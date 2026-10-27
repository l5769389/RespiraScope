import math

import pytest
from fastapi.testclient import TestClient

from ct_breath.app import create_app
from ct_breath.core.config import AppConfig


@pytest.fixture
def client():
    return TestClient(create_app(AppConfig(enable_mock_signal=True, enable_front_console=False)))


def test_custom_offline_band_is_applied_without_changing_realtime(client):
    raw = [[i, 500 + 100 * math.sin(i * math.pi / 100)] for i in range(1000)]
    before = client.get('/stream/status').json()['data']['filter_config']
    default = client.post('/applyFilter', json={'raw_data': raw}).json()
    response = client.post('/applyFilter', json={'raw_data': raw, 'filter_config': {
        'bandpass_mode': 'custom', 'lowpass_cutoff': .03, 'highpass_cutoff': 2,
    }})
    assert response.status_code == 200
    result = response.json()
    assert result['filter_config']['lowpass_cutoff'] == .03
    assert result['filter_config']['highpass_cutoff'] == 2
    assert result['data'] != default['data']
    assert client.get('/stream/status').json()['data']['filter_config'] == before


@pytest.mark.parametrize('extra', [
    {'lowpass_cutoff': 2, 'highpass_cutoff': 1},
    {'lowpass_cutoff': .1, 'highpass_cutoff': .1},
    {'lowpass_cutoff': 0},
    {'sampling_rate': 4, 'highpass_cutoff': 2},
    {'sampling_rate': 0},
])
def test_invalid_band_rejected_before_filtering(client, extra):
    assert client.post('/applyFilter', json={'filter_config': {
        'bandpass_mode': 'custom', **extra,
    }}).status_code == 422


def test_sensitivity_redetects_existing_curve_without_touching_live_filter(client, monkeypatch):
    from ct_breath.processing.processor import SignalProcessor

    async def unexpected_filter(*args, **kwargs):
        pytest.fail('Detection-only request must not filter the signal')

    monkeypatch.setattr(SignalProcessor, 'filter_data', unexpected_filter)
    # Alternating deep and shallow cycles, with enough spacing to pass the distance rule.
    points = [[i, 500 + (100 if (i // 200) % 2 == 0 else 25) * math.sin(i * math.pi / 100)]
              for i in range(2000)]
    before = client.get('/stream/status').json()['data']['filter_config']
    results = []
    for ratio in [.45, .15]:
        response = client.post('/detectPeaks', json={
            'filtered_data': points, 'filter_config': {'peak_threshold_ratio': ratio},
        })
        assert response.status_code == 200
        results.append(response.json())
    assert len(results[1]['peak']) > len(results[0]['peak'])
    assert client.get('/stream/status').json()['data']['filter_config'] == before
