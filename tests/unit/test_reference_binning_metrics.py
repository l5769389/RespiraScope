import numpy as np
import pytest
from scripts.reports.reference_binning_metrics import (reference_labels, compare_reference, summarize_reference,
                                      compare_base_span, summarize_base_span)


def test_reference_triangular_breath_known_time_bins_direction_and_bounds():
    # Valley at 10, peak at 20, valley at 30; clean values rise from 0 to 10.
    clean=np.r_[np.arange(10, 0, -1), np.arange(0, 10), np.arange(10, 0, -1), np.arange(0, 11)]
    ref=reference_labels(clean, (2, 8))
    assert ref['time'][10:20].tolist() == [0,0,1,1,2,2,3,3,4,4]
    assert ref['time'][20:30].tolist() == [5,5,6,6,7,7,8,8,9,9]
    assert ref['fixed'][[10,11,19,20,21,29]].tolist() == [-1]*6
    assert ref['fixed'][[12,15,18,22,25,28]].tolist() == [0,2,4,5,7,9]


def test_mismatch_scores_same_points_and_counts_false_in_range_as_error():
    actual={'time':np.array([0,1,2,3]),'fixed':np.array([0,1,-1,3])}
    reference={'time':np.array([0,2,2,3]),'fixed':np.array([0,-1,2,3])}
    result=compare_reference(actual,reference,np.array([1,1,1,0],bool))
    assert result['scored_points']==2
    assert result['scored_percent']==50
    assert result['modes']['time']['mismatch_percent']==50
    assert result['modes']['fixed']['mismatch_percent']==50


def test_empty_is_missing_and_aggregate_uses_sample_weights():
    reference={'time':np.zeros(4,int),'fixed':np.zeros(4,int)}
    empty=compare_reference(reference, reference, np.zeros(4,bool))
    assert empty['modes']['time']['mismatch_percent'] is None
    small=compare_reference({'time':np.ones(4,int),'fixed':np.zeros(4,int)}, reference, np.array([1,0,0,0],bool))
    full=compare_reference(reference, reference, np.ones(4,bool))
    result=summarize_reference([empty,small,full])
    assert result['scored_runs']==2
    assert result['modes']['time']['mismatch_percent']==pytest.approx(20)
    assert summarize_reference([empty])['modes']['time']['mismatch_percent'] is None


@pytest.mark.parametrize('gain, expected', [(0.8, -20), (1.2, 20), (1, 0)])
def test_base_span_measures_gain_independent_of_offset(gain, expected):
    clean=np.linspace(-50, 50, 1001)
    result=compare_base_span(clean, gain*clean+70, np.ones(len(clean), bool))
    assert result['clean_span']==pytest.approx(90)
    assert result['change_percent']==pytest.approx(expected)


def test_base_span_excludes_artifacts_at_identical_timestamps():
    clean=np.arange(101, dtype=float)
    filtered=.5*clean
    filtered[-20:]=10000
    valid=np.arange(101)<81
    result=compare_base_span(clean, filtered, valid)
    assert result['scored_points']==81
    assert result['change_percent']==pytest.approx(-50)


def test_base_span_missing_data_and_run_mean():
    empty=compare_base_span([0, 1], [0, 1], [False, False])
    flat=compare_base_span([5, 5], [4, 6], [True, True])
    assert empty['change_percent'] is None
    assert flat['change_percent'] is None
    a=compare_base_span([0, 10], [0, 8], [True, True])
    b=compare_base_span([0, 5, 10], [0, 5.5, 11], [True]*3)
    result=summarize_base_span([empty, flat, a, b])
    assert result['change_percent']==pytest.approx(-5)
    assert result['scored_runs']==2
    assert result['scored_points']==5
    assert summarize_base_span([empty, flat])['change_percent'] is None
