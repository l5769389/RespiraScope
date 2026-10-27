"""The optional offline low-pass must preserve baseline without legitimizing artifacts."""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from ct_breath.app import create_app
from ct_breath.core.config import AppConfig
from tests.support.offline import apply, wave, record_bins


@pytest.fixture
def client():
    return TestClient(create_app(AppConfig(enable_front_console=False)))


def test_lowpass_preserves_slow_baseline_and_rejects_high_frequency_noise(client):
    t = np.arange(9000)/50
    clean = 180 + 28*np.sin(2*np.pi*t/45) + 60*np.sin(2*np.pi*.3*t)
    raw = clean + 12*np.sin(2*np.pi*8*t)
    result = apply(client, raw, offline_filter='baseline_lowpass')
    y = np.asarray(result['data'])[:, 1]
    assert np.sqrt(np.mean((y[1000:-1000]-clean[1000:-1000])**2)) < 1
    assert result['filter_config']['offline_filter'] == 'baseline_lowpass'
    assert result['processingQuality']['baselines'][0]['status'] == 'preserved'
    original = apply(client, raw)
    assert np.sqrt(np.mean((np.asarray(original['data'])[1000:-1000,1]-clean[1000:-1000])**2)) > 10


def test_lowpass_does_not_recenter_or_use_inactive_lower_cutoff(client):
    raw = wave(60)
    a = apply(client, raw, offline_filter='baseline_lowpass', bandpass_mode='custom',
              lowpass_cutoff=.03, highpass_cutoff=1, restore_baseline=False)
    b = apply(client, raw, offline_filter='baseline_lowpass', bandpass_mode='custom',
              lowpass_cutoff=3, highpass_cutoff=1)
    assert a['data'] == b['data']
    assert a['filter_config']['restore_baseline'] is True
    assert abs(np.mean(np.asarray(a['data'])[1000:2000,1])-180) < 2


def test_lowpass_keeps_local_cough_excluded_and_other_breaths_available(client):
    raw = wave(100)
    raw[2500:2520] += np.linspace(400,0,20)
    result = apply(client, raw, offline_filter='baseline_lowpass')
    intervals = result['processingQuality']['invalidIntervals']
    assert any(i['reason']=='motion' and i['start']<=2500<i['end'] for i in intervals)
    bins = record_bins(raw, result, 'amplitude')
    assert any(b['end'] < 2400 for b in bins)
    assert any(b['start'] > 2700 for b in bins)
    assert all(not (b['start']<i['end'] and b['end']>i['start']) for b in bins for i in intervals)
    assert result['filter_config'].get('offline_filter') == 'baseline_lowpass'


def test_lowpass_preserves_dc_in_short_segments_without_bridging_missing_samples(client):
    raw = [[0,300.0]] + [[i+100,200.0] for i in range(1000)]
    response = client.post('/applyFilter',json={'raw_data':raw,'filter_config':{
        'offline_filter':'baseline_lowpass','processing_mode':'amplitude'}})
    assert response.status_code == 200
    result = response.json()
    assert result['data'][0] == [0,300.0]
    assert [p[0] for p in result['data']] == [p[0] for p in raw]
    assert all(abs(v-200)<.1 for _,v in result['data'][1:])
    assert not result['peak'] and not result['valley']


@pytest.mark.parametrize('endpoint',['/startReceive','/setRTFilterParams'])
def test_offline_lowpass_cannot_change_live_pipeline(client, endpoint):
    before = client.get('/stream/status').json()['data']['filter_config']
    response = client.post(endpoint,json={'offline_filter':'baseline_lowpass'})
    assert response.status_code == 422
    assert client.get('/stream/status').json()['data']['filter_config'] == before


def test_legacy_configuration_keeps_identical_bandpass_output(client):
    raw = wave(60)
    old = apply(client,raw)
    explicit = apply(client,raw,offline_filter='bandpass')
    assert old['data'] == explicit['data']
    assert old['peak'] == explicit['peak']
    assert old['filter_config'].get('offline_filter') == 'bandpass'


def test_slow_baseline_does_not_hide_shallow_breaths_or_change_extremum_values(client):
    t = np.arange(9000)/50
    raw = 250 + 100*np.sin(2*np.pi*t/60) + 20*np.sin(2*np.pi*.3*t)
    result = apply(client,raw,offline_filter='baseline_lowpass')
    assert 45 <= len(result['peak']) <= 55
    assert result['metrics']['bpm'] == pytest.approx(18, abs=.5)
    values = dict(result['data'])
    assert all(p['value']==values[p['sequence']] for p in result['peak']+result['valley'])
    # Sensitivity-only recalculation must use the same low-pass-aware detector.
    redetect = client.post('/detectPeaks',json={'filtered_data':result['data'],
        'filter_config':result['filter_config'],
        'invalid_intervals':result['processingQuality']['invalidIntervals']}).json()
    assert redetect['peak'] == result['peak']
    assert redetect['valley'] == result['valley']


def test_finished_record_defaults_to_lowpass_without_changing_live_config(client):
    system = client.app.state.session_manager.get_system('offline-default')
    manager = system.record_manager
    manager.record_start_time, manager.record_end_time = 1700000000, 1700000020
    manager.record_start_sequence, manager.record_end_sequence = 1000, 2000
    manager.raw_record_queue.extend([[i, float(v)] for i,v in enumerate(wave(80))])
    before = system.signal_processor.filter_config.model_dump()
    response = client.post('/record/end', headers={'X-RespiraScope-Session':'offline-default','Accept':'application/vnd.respirascope.record.v6+json'})
    assert response.status_code == 200, response.text
    record = response.json()['data']
    assert record['filterConfig']['offline_filter'] == 'baseline_lowpass'
    assert record['filterConfig']['highpass_cutoff'] == 2
    assert record['processingQuality']['baselines'][0]['status'] == 'preserved'
    assert system.signal_processor.filter_config.model_dump() == before
