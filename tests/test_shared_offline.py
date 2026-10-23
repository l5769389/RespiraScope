"""Binning basis must not change the offline signal or its context."""
import math
import pytest
from fastapi.testclient import TestClient
from ct_breath.app import create_app
from ct_breath.config import AppConfig, get_config
from ct_breath.frontend_static import runtime_config_payload
from ct_breath.breath_process.breath_process_manager import BreathProcessSystem
from ct_breath.breath_process.filter_context import recording_padding, mode_padding


@pytest.mark.parametrize('source', ['dataclass', 'new_file', 'missing_fields'])
def test_default_context_is_200_points_in_capture_and_runtime(tmp_path, source):
    path = tmp_path/'breath.toml'
    if source == 'missing_fields':
        path.write_text('[record]\n')
    config = AppConfig() if source == 'dataclass' else get_config(path)
    assert recording_padding(config) == (200, 200)
    manager = BreathProcessSystem(config).record_manager
    assert (manager.pre_points, manager.post_points) == (200, 200)
    browser = runtime_config_payload(config)['record']
    api = TestClient(create_app(config)).get('/runtime/config').json()['data']['record']
    assert browser['prePoints'] == browser['postPoints'] == 200
    assert api['pre_points'] == api['post_points'] == 200


@pytest.mark.parametrize('basis', ['time', 'amplitude'])
def test_default_lowpass_uses_200_real_points_per_side(basis):
    client = TestClient(create_app(AppConfig()))
    raw = [[i, 180+80*math.sin(i*2*math.pi/170)] for i in range(4000)]
    response = client.post('/applyFilter', json={'raw_data':raw,
        'filter_config':{'processing_mode':basis,'offline_filter':'baseline_lowpass'},
        'record_start_sequence':1000,'record_end_sequence':2499})
    assert response.status_code == 200
    data = response.json()['data']
    assert [p[0] for p in data] == list(range(800, 2700))


def test_basis_only_changes_labels_not_filter_result(tmp_path):
    path = tmp_path/'breath.toml'
    path.write_text('[record]\ntime_pre_points=100\ntime_post_points=150\namplitude_pre_points=300\namplitude_post_points=400\n')
    client = TestClient(create_app(get_config(path)))
    raw = [[i, 180+80*math.sin(i*2*math.pi/170)] for i in range(4000)]
    results = []
    for basis in ['time', 'amplitude']:
        r = client.post('/applyFilter', json={'raw_data':raw,
            'filter_config':{'processing_mode':basis,'offline_filter':'baseline_lowpass',
                'bandpass_mode':'custom','highpass_cutoff':1.3,'gaussian_sigma':2.2},
            'record_start_sequence':1000,'record_end_sequence':2499})
        assert r.status_code == 200
        results.append(r.json())
    for key in ['data','peak','valley','processingQuality']:
        assert results[0][key] == results[1][key]
    assert results[0]['data'][0][0] == 700
    assert results[0]['data'][-1][0] == 2899


def test_shared_padding_overrides_legacy_and_reloads_only_on_restart(tmp_path):
    path = tmp_path/'breath.toml'
    path.write_text('[record]\npre_points=0\npost_points=120\ntime_pre_points=100\namplitude_pre_points=300\n')
    config = get_config(path)
    assert recording_padding(config) == (0,120)
    assert mode_padding(config,'time') == mode_padding(config,'amplitude') == (0,120)
    path.write_text('[record]\npre_points=200\npost_points=250\n')
    assert recording_padding(config) == (0,120)
    assert recording_padding(get_config(path)) == (200,250)
