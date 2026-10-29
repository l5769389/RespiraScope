import pytest

from ct_breath.binning.data import build_binning_timeline, build_binning_data


def test_statuses_cover_record_without_overlaps_and_exclusion_wins():
    result = build_binning_timeline(
        [[0, 0], [10, 10], [20, 20], [30, 30], [40, 40]],
        [{'start':0,'end':20,'direction':'inhale','bin':1}],
        [{'start':10,'end':15,'reason':'motion'}, {'start':12,'end':18,'reason':'filter_edge'}],
        {'basis':'time','totalBins':10,'inhaleRising':True}, 0, 40, 50, 25)
    rows = result['intervals']
    assert [(r['start'],r['end'],r['status']) for r in rows] == [
        (0,10,'valid'),(10,18,'excluded'),
        (18,20,'valid'),(20,40,'unassigned')]
    assert all('reasons' not in r for r in rows)
    assert rows[1]['bin'] is None and rows[1]['direction'] is None


def test_unassigned_ranges_merge_without_reason_subcategories():
    result = build_binning_timeline([[0,0],[10,10],[20,20]], [], [],
        {'basis':'time'}, 0, 30, 50, 25)
    assert [(r['start'],r['end'],r['status']) for r in result['intervals']] == [(0,30,'unassigned')]


def test_gap_and_context_do_not_become_valid_bins():
    result = build_binning_timeline([[-10,0],[0,1],[10,2],[50,3],[60,4],[70,5]], [],
        [{'start':11,'end':50,'reason':'gap'}], {'basis':'time'}, 0,60,50,25)
    rows=result['intervals']
    assert rows[0]['start']==0 and rows[-1]['end']==60
    assert any(r['status']=='excluded' and r['start']==11 and r['end']==50 for r in rows)
    assert not any(r['status']=='valid' for r in rows)


def test_compact_bins_use_original_array_indexes_and_merge_adjacent_ranges():
    result = build_binning_data([[100,0],[102,1],[104,2],[106,3],[108,4],[110,5]],
        [{'start':100.1,'end':104,'direction':'inhale','bin':1},
         {'start':104,'end':108,'direction':'inhale','bin':1},
         {'start':108,'end':110,'direction':'exhale','bin':2}],
        [], {'basis':'time','totalBins':4},100,110)
    assert result == {'version':5,'inhaleRising':True,
                      'bins':{'inhale':[[[1,4]],[]],'exhale':[[],[[4,5]]]},
                      'excluded':{'quality':[],'range':[]},'unassigned':[[0,1]]}


def test_compact_bins_never_include_excluded_sample_or_renumber_after_it():
    result=build_binning_data([[i, i] for i in range(8)],
        [{'start':0,'end':7,'direction':'inhale','bin':1}],
        [{'start':2,'end':4,'reason':'motion'}],{'basis':'time','totalBins':4},0,7)
    assert result == {'version':5,'inhaleRising':True,
                      'bins':{'inhale':[[[0,2],[4,7]],[]],'exhale':[[],[]]},
                      'excluded':{'quality':[[2,4]],'range':[]},'unassigned':[]}


def test_overlapping_exclusions_are_merged_without_duplicate_samples():
    result=build_binning_data([[i, i] for i in range(12)],
        [{'start':0,'end':2,'direction':'exhale','bin':1}],
        [{'start':3,'end':7,'reason':'motion'},{'start':5,'end':9,'reason':'filter_edge'}],
        {'basis':'time','totalBins':4,'inhaleRising':False},0,11)
    assert result['inhaleRising'] is False
    assert result['bins']=={'inhale':[[],[]],'exhale':[[[0,2]],[]]}
    assert result['excluded']=={'quality':[[3,9]],'range':[]}
    assert result['unassigned']==[[2,3],[9,11]]


def test_fixed_bounds_exclude_outside_samples_without_extrema():
    result=build_binning_data([[i,i] for i in range(21)],[],[],
        {'basis':'amplitude','amplitudeMode':'fixed','lower':5,'upper':15},0,20)
    assert result['excluded']=={'quality':[],'range':[[0,5],[16,20]]}
    assert result['unassigned']==[[5,16]]


def test_fixed_bounds_and_quality_exclusions_take_precedence_over_manual_bins():
    points = [[i, i] for i in range(21)]
    options = {'basis':'amplitude','amplitudeMode':'fixed','lower':5,'upper':15}
    bins = [{'start':0,'end':20,'direction':'inhale','bin':1}]
    result = build_binning_data(points,bins,[{'start':14,'end':18}],options,0,20)
    assert result['excluded'] == {'quality':[[14,18]],'range':[[0,5],[18,20]]}
    assert result['bins']['inhale'][0] == [[5,14]]
    assert result['unassigned'] == []
    # Widening the bounds only removes range exclusions, never quality exclusions.
    widened = build_binning_data(points,bins,[{'start':14,'end':18}],
        {**options,'lower':0,'upper':20},0,20)
    assert widened['excluded'] == {'quality':[[14,18]],'range':[]}
    assert widened['bins']['inhale'][0] == [[0,14],[18,20]]


def test_bounds_are_inclusive_for_both_signal_directions_and_clipped_to_record():
    for values in [[0,5,15,20,0],[20,15,5,0,20]]:
        result = build_binning_data(list(enumerate(values)),[],[],
            {'basis':'amplitude','amplitudeMode':'fixed','lower':5,'upper':15},1,4)
        assert result['excluded'] == {'quality':[],'range':[[3,4]]}
        assert result['unassigned'] == [[1,3]]


def test_amplitude_bounds_do_not_exclude_time_or_free_binning():
    for options in [{'basis':'time'}, {'basis':'amplitude','amplitudeMode':'free'}]:
        result = build_binning_data([[i,i] for i in range(21)],[],[],
            {**options,'lower':5,'upper':15},0,20)
        assert result['excluded'] == {'quality':[],'range':[]}
        assert result['unassigned'] == [[0,20]]


@pytest.mark.parametrize('lower,upper', [(5,5),(10,5),(None,5),(0,float('inf'))])
def test_invalid_fixed_bounds_raise_instead_of_returning_unassigned(lower, upper):
    with pytest.raises(ValueError, match='lower < upper'):
        build_binning_data([[0,0],[1,1]],[],[],
            {'basis':'amplitude','amplitudeMode':'fixed','lower':lower,'upper':upper},0,1)


def test_outside_samples_do_not_bridge_missing_data_or_duplicate_assignments():
    points = [[0,0],[1,10],[40,20],[41,10],[42,5]]
    result = build_binning_data(points,[],[],
        {'basis':'amplitude','amplitudeMode':'fixed','lower':5,'upper':15},0,42)
    assert result['excluded'] == {'quality':[],'range':[[0,1],[2,3]]}
    assert result['unassigned'] == [[1,2],[3,4]]
    timeline = build_binning_timeline(points,[],[],
        {'basis':'amplitude','amplitudeMode':'fixed','lower':5,'upper':15},0,42)
    assert [(r['start'],r['end'],r['status']) for r in timeline['intervals']] == [
        (0,1,'excluded'),(1,40,'unassigned'),(40,41,'excluded'),(41,42,'unassigned')]


def test_adjacent_exclusion_types_remain_distinct_and_cover_samples_once():
    result=build_binning_data([[i,i] for i in range(21)],[],
        [{'start':3,'end':7},{'start':6,'end':10}],
        {'basis':'amplitude','amplitudeMode':'fixed','lower':5,'upper':15},0,20)
    assert result['excluded'] == {'quality':[[3,10]],'range':[[0,3],[16,20]]}
    assert result['unassigned'] == [[10,16]]
    assigned=[i for intervals in [*result['excluded'].values(),result['unassigned']]
              for a,b in intervals for i in range(a,b)]
    assert sorted(assigned)==list(range(20))
