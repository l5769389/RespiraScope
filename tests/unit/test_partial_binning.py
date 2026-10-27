"""Local binning must recover measured segments, never bridge excluded data."""
from tests.support.binning import FIXED, TIME, triangle, compute, missed_turn
import pytest
from ct_breath.binning.respiratory import build_respiratory_bins


def test_fixed_keeps_exhalation_without_a_terminal_valley():
    bins = compute(triangle())
    assert [(b['direction'],b['bin']) for b in bins] == [('inhale',i) for i in range(1,6)] + [('exhale',i) for i in range(1,6)]
    assert bins[-1]['end'] == 100


def test_fixed_stops_before_invalid_samples_and_retains_only_reached_bins():
    source = triangle()
    source['processingQuality'] = {'invalidIntervals':[{'start':76,'end':101,'reason':'motion'}]}
    bins = compute(source)
    assert [(b['bin'], b['start'], b['end']) for b in bins if b['direction']=='exhale'] == [(1,50,60),(2,60,70),(3,70,75)]


def test_fixed_keeps_leading_segment_and_reverses_direction_with_sensor():
    source = triangle(); source['valleys'] = [[100,0]]
    bins = compute(source, {**FIXED,'inhaleRising':False})
    assert bins[0]['direction'] == 'exhale'
    assert bins[0]['start'] == 0
    assert bins[-1]['direction'] == 'inhale'


@pytest.mark.parametrize('options', [TIME,FIXED])
def test_missing_interior_turn_can_be_recovered_from_clean_measured_curve(options):
    bins = compute(missed_turn(), options)
    assert len(bins) == 10
    assert bins[0]['direction']=='exhale' and bins[4]['end']==50
    assert bins[5]['direction']=='inhale' and bins[-1]['end']==100


def test_time_does_not_invent_terminal_valley_or_cross_an_artifact():
    bins = compute(triangle(), TIME)
    assert len(bins) == 5 and all(b['direction']=='inhale' for b in bins)
    source=missed_turn()
    source['processingQuality']={'invalidIntervals':[{'start':45,'end':56,'reason':'motion'}]}
    assert compute(source,TIME) == []


def test_time_does_not_join_multiple_breaths_as_one_missing_turn():
    source={'filtered':[[i,abs((i%100)-50)] for i in range(201)],'peaks':[[0,50],[200,50]],'valleys':[]}
    assert compute(source,TIME) == []


def test_short_flat_or_unanchored_tail_has_no_direction():
    for values in ([50]*40, [50,49.8,50]*12, [50,0,50]):
        source={'filtered':[[i,y] for i,y in enumerate(values)],'peaks':[[0,50]],'valleys':[]}
        assert compute(source) == []
    assert compute({**triangle(),'peaks':[],'valleys':[]}) == []


def test_fixed_does_not_extend_direction_beyond_a_clear_reversal():
    source={'filtered':[[i,abs(i-50)] for i in range(101)],'peaks':[[0,50]],'valleys':[]}
    bins=compute(source)
    assert bins and all(b['direction']=='exhale' and b['end']<=50 for b in bins)


def test_fixed_never_interpolates_across_gap_or_nonfinite_sample():
    source=triangle(); source['filtered']=[p for p in source['filtered'] if p[0]<76 or p[0]>105]
    source['filtered'] += [[110,0],[120,10]]
    bins=compute(source)
    assert any(b['direction']=='exhale' for b in bins)
    assert all(b['end']<=75 for b in bins)
    source=triangle();source['filtered'][76][1]=float('nan')
    assert all(b['end']<=75 for b in compute(source))
