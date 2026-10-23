"""Checks for the offline comparison report's timing scorer, not product behavior."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest

spec=importlib.util.spec_from_file_location('timing_metrics',Path(__file__).parents[1]/'scripts/filter_timing_metrics.py')


def scorer():
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.score_timing


def test_known_shift_missing_event_and_internal_boundaries():
    score=scorer()
    truth={'peak':[100,300,500],'valley':[200,400,600]}
    preds={'a':{k:[v+5 for v in arr] for k,arr in truth.items()},'b':truth}
    result=score(truth,preds,np.ones(800,dtype=bool),50,40)
    assert result['modes']['a']['errors_ms']==[100]*6
    assert result['modes']['b']['errors_ms']==[0]*6
    assert result['modes']['a']['boundary_errors_ms']==pytest.approx([100]*20)
    assert result['paired_half_breaths']==5
    preds['a']['peak']=preds['a']['peak'][:-1]
    result=score(truth,preds,np.ones(800,dtype=bool),50,40)
    assert result['modes']['a']['missed']==1
    assert result['modes']['a']['extra']==0
    assert result['paired_half_breaths']==3


def test_never_matches_across_invalid_region_and_counts_extra_events():
    score=scorer()
    valid=np.ones(800,dtype=bool);valid[250:350]=False
    truth={'peak':[100,300,500],'valley':[200,400,600]}
    preds={'a':{'peak':[100,300,500,700],'valley':[200,400,600]},'b':truth}
    result=score(truth,preds,valid,50,30)
    assert result['modes']['a']['reference']==5
    assert result['modes']['a']['extra']==1
    assert result['paired_half_breaths']==3
    assert len(result['modes']['a']['boundary_errors_ms'])==12


def test_matching_margin_does_not_count_shifted_boundary_event_as_extra():
    truth={'peak':[35,235],'valley':[135,335]}
    shifted={kind:[i+5 for i in values] for kind,values in truth.items()}
    result=scorer()(truth,{'a':shifted,'b':truth},np.ones(400,dtype=bool),50,40)
    assert result['modes']['a']['reference']==3
    assert result['modes']['a']['matched']==3
    assert result['modes']['a']['extra']==0
    assert result['modes']['a']['errors_ms']==[100]*3
