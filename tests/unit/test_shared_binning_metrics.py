import numpy as np
import pytest
from scripts.reports.compare_shared_binning import labels_from_bins, within_bin_spread, default_bounds


def test_fractional_intervals_use_half_open_labels():
    bins=[{'start':.5,'end':2.,'direction':'inhale','bin':1},
          {'start':2.,'end':3.5,'direction':'exhale','bin':5}]
    assert labels_from_bins(bins,0,5).tolist()==[-1,0,9,9,-1]


def test_dispersion_uses_common_samples_and_does_not_score_empty_as_zero():
    truth=np.array([0.,2.,10.,12.,999.]);labels=np.array([0,0,5,5,5]);mask=np.array([1,1,1,1,0],bool)
    assert within_bin_spread(truth,labels,mask,10)==pytest.approx(10.)
    assert within_bin_spread(truth,labels,np.zeros(5,bool),10) is None


def test_report_bounds_match_record_only_floor_quantiles():
    data=[[i,-1000 if i<100 else 10000 if i>=200 else i-100] for i in range(300)]
    assert default_bounds(data,{'invalidIntervals':[{'start':190,'end':200}]},100,199)==[4,84]
