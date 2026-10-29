"""Editing must preserve sample ownership and never reverse respiratory direction."""
from itertools import combinations

import pytest

from ct_breath.binning.data import build_binning_data, build_binning_timeline
from tests.support.binning import compute


MODES = [dict(basis='time'), dict(basis='amplitude', amplitudeMode='free'),
         dict(basis='amplitude', amplitudeMode='fixed', lower=10, upper=40)]


def expand(intervals):
    return [i for a,b in intervals for i in range(a,b)]


@pytest.mark.parametrize('mode', MODES, ids=['time','free','fixed'])
@pytest.mark.parametrize('count', [4,6,8,10,12,16,20])
@pytest.mark.parametrize('inhale_rising', [True,False])
def test_all_marker_deletion_combinations_preserve_partition_and_direction(mode,count,inhale_rising):
    points=[[i,50-abs(i%100-50)] for i in range(201)]
    marks=[(0,'valleys'),(50,'peaks'),(100,'valleys'),(150,'peaks'),(200,'valleys')]
    options={**mode,'totalBins':count,'inhaleRising':inhale_rising}
    # Every subset models a different sequence of manual deletions.
    for size in range(6):
        for retained in combinations(marks,size):
            source={'filtered':points, **{key:[points[x] for x,k in retained if k==key]
                                          for key in ['peaks','valleys']}}
            bins=compute(source,options)
            result=build_binning_data(points,bins,[],options,10.5,189.25)
            groups=[*result['bins']['inhale'],*result['bins']['exhale'],
                    *result['excluded'].values(),result['unassigned']]
            # All stored samples inside the selected interval occur exactly once;
            # neither buffer samples nor the final right boundary are reassigned.
            assert sorted(i for group in groups for i in expand(group))==list(range(11,190))
            assert len(result['bins']['inhale'])==len(result['bins']['exhale'])==count//2
            for b in bins:
                rising=(b['direction']=='inhale')==inhale_rising
                assert 1<=b['bin']<=count//2
                # Ground truth is the four linear legs, independent of detected marks.
                for left,right,goes_up in [(0,50,True),(50,100,False),(100,150,True),(150,200,False)]:
                    if max(left,b['start'])<min(right,b['end'])-1e-8:
                        assert rising==goes_up, (retained,b)
            if size==5:
                # An exit exactly on a bound belongs to neither the half-open
                # bin interval nor the strictly-outside range exclusion.
                assert result['unassigned']==([[40,41],[90,91],[140,141]] if mode.get('amplitudeMode')=='fixed' else [])
            if size==0:
                assert not any(result['bins']['inhale']+result['bins']['exhale'])


@pytest.mark.parametrize('mode', MODES, ids=['time','free','fixed'])
def test_complete_manual_marks_never_override_quality_or_acquisition_gaps(mode):
    points=[[i,50-abs(i%100-50)] for i in range(201) if not 110<=i<140]
    invalid=[{'start':35,'end':65},{'start':55,'end':75}]
    source={'filtered':points,'peaks':[[50,50],[150,50]],'valleys':[[0,0],[100,0],[200,0]],
            'processingQuality':{'invalidIntervals':invalid}}
    mode={**mode,'totalBins':10,'inhaleRising':True}
    bins=compute(source,mode)
    timeline=build_binning_timeline(points,bins,invalid,mode,0,200)
    assert all(not (b['start']<140 and b['end']>109) for b in bins)
    result=build_binning_data(points,bins,invalid,mode,0,200)
    assert expand(result['excluded']['quality'])==list(range(35,75))
    quality=set(expand(result['excluded']['quality']))
    for group in [*result['bins']['inhale'],*result['bins']['exhale'],result['excluded']['range'],result['unassigned']]:
        assert not quality.intersection(expand(group))
    assert timeline['intervals'][0]['start']==0 and timeline['intervals'][-1]['end']==200
    assert all(a['end']==b['start'] for a,b in zip(timeline['intervals'],timeline['intervals'][1:]))
    assert all(r['status']!='valid' for r in timeline['intervals'] if r['start']<140 and r['end']>110)
