import numpy as np
import pytest
from scipy import signal
from scipy.ndimage import gaussian_filter1d
from ct_breath.processing import quality as offline_quality
from ct_breath.models import FilterConfig


@pytest.mark.parametrize('length', [20,250])
def test_one_filtered_curve_across_motion_boundaries(monkeypatch, length):
    n=2000
    raw=180+80*np.sin(2*np.pi*.3*np.arange(n)/50)
    raw[900:900+length]+=300
    original=raw.copy()
    motion=np.zeros(n,bool);motion[900:900+length]=True
    monkeypatch.setattr(offline_quality,'artifact_masks',lambda x,fs:(np.zeros(n,bool),motion))
    config=FilterConfig(offline_filter='baseline_lowpass',highpass_cutoff=2,lowpass_order=4,gaussian_sigma=1)
    working=raw.copy()
    if length<=50:
        working[900:900+length]=np.interp(np.arange(900,900+length),[899,900+length],[raw[899],raw[900+length]])
    sos=signal.butter(4,2,btype='lowpass',fs=50,output='sos')
    expected=np.round(gaussian_filter1d(signal.sosfiltfilt(sos,working),1),1)
    actual,quality=offline_quality.filter_offline(raw,np.arange(n),config)
    np.testing.assert_allclose(actual,expected)
    np.testing.assert_array_equal(raw,original)
    assert any(i['reason']=='motion' and i['start']==900 and i['end']==900+length for i in quality['invalidIntervals'])
    if length==20:
        assert np.max(np.abs(np.diff(actual[880:940])))<5
