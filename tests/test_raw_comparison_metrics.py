import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from raw_comparison_metrics import compare_to_raw, summarize_raw_comparison


@pytest.mark.parametrize('shift',[6,-4,0])
def test_lag_sign_and_gain_independence(shift):
    t=np.arange(3000)/50
    raw=100+30*np.sin(2*np.pi*.23*t)+7*np.sin(2*np.pi*.46*t+.3)
    filtered=.8*np.roll(raw,shift)+15
    result=compare_to_raw(raw,filtered,np.ones(len(t),bool),50,14)
    assert result['lag_ms']==pytest.approx(shift*20)


def test_point_difference_is_distinct_from_amplitude_span():
    raw=np.tile(np.arange(100,dtype=float),30)
    out=compare_to_raw(raw,raw+5,np.ones(len(raw),bool),50,18)
    assert out['mae_units']==pytest.approx(5)
    assert out['span_change_percent']==pytest.approx(0)
    out=compare_to_raw(raw,raw*.8,np.ones(len(raw),bool),50,18)
    assert out['span_change_percent']==pytest.approx(-20)


def test_short_disconnected_valid_regions_do_not_become_a_phase_estimate():
    raw=np.sin(np.arange(3000)/50)
    valid=np.arange(3000)%100<50
    out=compare_to_raw(raw,raw,valid,50,18)
    assert out['lag_ms'] is None
    assert out['mae_units']==0
    summary=summarize_raw_comparison([out])
    assert summary['lag_runs']==0 and summary['lag_ms_median'] is None
