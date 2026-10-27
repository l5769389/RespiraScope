"""Shared acquisition padding, partial context and restart-only settings."""
import math

import pytest
from fastapi.testclient import TestClient

from ct_breath.app import create_app
from ct_breath.core.config import get_config
from ct_breath.application.service import BreathProcessSystem


def configured(tmp_path, text):
    path = tmp_path/'breath.toml'
    path.write_text('[record]\n'+text)
    return get_config(path)


@pytest.mark.parametrize('mode', ['time','amplitude'])
def test_custom_context_is_shared_by_capture_and_filtering(tmp_path,mode):
    config=configured(tmp_path,'pre_points=300\npost_points=400\n')
    client=TestClient(create_app(config))
    raw=[[i,180+90*math.sin(i*2*math.pi/170)] for i in range(4000)]
    result=client.post('/applyFilter',json={'raw_data':raw,'filter_config':{'processing_mode':mode},
        'record_start_sequence':1000,'record_end_sequence':2499}).json()
    assert result['data'][0][0] == 700
    assert result['data'][-1][0] == 2899
    manager=BreathProcessSystem(config).record_manager
    assert manager.pre_points == 300 and manager.post_points == 400


def test_short_available_context_is_used_without_padding(tmp_path):
    config=configured(tmp_path,'pre_points=200\npost_points=200\n')
    client=TestClient(create_app(config))
    raw=[[i,180+90*math.sin(i*2*math.pi/170)] for i in range(950,2600)]
    response=client.post('/applyFilter',json={'raw_data':raw,'filter_config':{'processing_mode':'time'},
        'record_start_sequence':1000,'record_end_sequence':2499})
    assert response.status_code == 200
    assert [p[0] for p in response.json()['data']] == [p[0] for p in raw]


def test_zero_padding_and_restart_loading(tmp_path):
    config=configured(tmp_path,'pre_points=0\npost_points=0\n')
    client=TestClient(create_app(config))
    raw=[[i,180+90*math.sin(i*2*math.pi/170)] for i in range(4000)]
    request={'raw_data':raw,'record_start_sequence':1000,'record_end_sequence':2499}
    assert len(client.post('/applyFilter',json=request).json()['data']) == 1500
    config.config_path.write_text('[record]\npre_points=100\npost_points=100\n')
    assert len(client.post('/applyFilter',json=request).json()['data']) == 1500
    new_client=TestClient(create_app(get_config(config.config_path)))
    assert len(new_client.post('/applyFilter',json=request).json()['data']) == 1700


def test_incomplete_or_reversed_record_range_is_rejected(tmp_path):
    client=TestClient(create_app(configured(tmp_path,'')))
    for fields in ({'record_start_sequence':10},{'record_start_sequence':20,'record_end_sequence':10}):
        assert client.post('/applyFilter',json=fields).status_code == 422
