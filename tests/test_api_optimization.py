import json
import math

import pytest
from fastapi.testclient import TestClient

from ct_breath.app import create_app
from ct_breath.config import AppConfig
from ct_breath.breath_process.record_manager import RecordManager
from ct_breath.http.schemas import FilterConfig

COMPACT = 'application/vnd.respirascope.record.v5+json'


@pytest.fixture
def client():
    return TestClient(create_app(AppConfig(enable_mock_signal=True, enable_front_console=False)))


@pytest.mark.parametrize('field,path', [('raw_data','/applyFilter'), ('filtered_data','/detectPeaks')])
@pytest.mark.parametrize('points', [[[1]], [[1,2,3]], [[1,'nan']], [[2,1],[1,2]], [[1,2],[1,3]], [[-1,2]], [[1.5,2]]])
def test_sample_data_has_explicit_validation(client, field, path, points):
    response = client.post(path, json={field:points})
    assert response.status_code == 422
    assert response.json()['detail']


def test_record_transport_is_compact_opt_in_and_keeps_filter_config(client, monkeypatch):
    system = client.app.state.session_manager.get_system('transport')
    manager = RecordManager()
    manager.record_start_sequence, manager.record_end_sequence = 100, 900
    manager.record_start_time, manager.record_end_time = 1700000000, 1700000016
    points = [[i, 500+100*math.sin(i*math.pi/100)] for i in range(1000)]
    manager.raw_record_queue.extend(points)
    config = FilterConfig(bandpass_mode='custom',lowpass_cutoff=.05,highpass_cutoff=1.5,peak_threshold_ratio=.15)
    payload = manager.build_record_data(config,filtered_data=points,peak_data=[[250,600],[450,600]],valley_data=[[150,400],[350,400],[550,400]])
    async def end(): return payload
    monkeypatch.setattr(system,'stop_record_and_filter',end)
    headers={'X-RespiraScope-Session':'transport','Accept-Encoding':'identity'}
    legacy=client.post('/record/end',headers=headers)
    compact=client.post('/record/end',headers={**headers,'Accept':COMPACT})
    assert legacy.status_code == compact.status_code == 200
    assert legacy.json()['filter_config'] == config.model_dump()
    data=compact.json()['data']
    assert data['version'] == 5
    assert data['filterConfig'] == config.model_dump()
    assert data['raw'] == points
    assert data['filtered'] == points
    assert 'binning' not in data
    assert data['respiratoryBins'] == payload['respiratoryBins']
    assert len(compact.content) < len(legacy.content)*.6
    assert 'Accept' in compact.headers['vary']
    compressed=client.post('/record/end',headers={**headers,'Accept':COMPACT,'Accept-Encoding':'gzip'})
    assert compressed.headers['content-encoding'] == 'gzip'
    assert compressed.json() == compact.json()
    for accept in (f'application/json, {COMPACT};q=0', f'application/json;q=1, {COMPACT};q=0.5'):
        rejected = client.post('/record/end', headers={**headers, 'Accept': accept})
        assert rejected.json() == legacy.json()


def test_nonfinite_json_number_returns_small_validation_error(client):
    response=client.post('/applyFilter',content='{"raw_data":[[0,1e999]]}',headers={'Content-Type':'application/json'})
    assert response.status_code == 422
    assert response.json()['detail'][0]['loc'] == ['body','raw_data',0,1]
    assert 'input' not in response.json()['detail'][0]


def test_short_valid_data_always_returns_an_array(client):
    response=client.post('/applyFilter',json={'raw_data':[[0,1],[1,2]]})
    assert response.status_code == 200
    assert response.json()['data'] == []
