"""Offline quality must not invent usable breathing intervals from corrupt data."""
from dataclasses import replace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from ct_breath.app import create_app
from ct_breath.config import AppConfig
from ct_breath.mock_sensor.breath_simulator import SCENARIO_PRESETS, generate_preview
from ct_breath.breath_process.record_manager import RecordManager
from ct_breath.breath_process.record_file import compact_record_data
from ct_breath.http.schemas import FilterConfig


@pytest.fixture
def client():
    return TestClient(create_app(AppConfig(enable_mock_signal=True, enable_front_console=False)))


def wave(seconds=180):
    t = np.arange(seconds * 50) / 50
    phase = 2 * np.pi * .3 * t
    return 180 + 110 * (.82*np.sin(phase) + .18*np.sin(2*phase-.8) + .06*np.sin(3*phase+.4))


def apply(client, values, **config):
    raw = [[i, float(y)] for i, y in enumerate(values)]
    response = client.post('/applyFilter', json={'raw_data':raw, 'filter_config':{
        'processing_mode':'amplitude', **config,
    }})
    assert response.status_code == 200
    return response.json()


def test_asymmetric_breathing_restores_dc_without_scaling_cycles(client):
    values = wave()
    result = apply(client, values)
    filtered = np.asarray(result['data'])[:,1]
    assert abs(np.mean(filtered[3000:6000] - values[3000:6000])) < 2
    assert .94 < np.std(filtered[3000:6000])/np.std(values[3000:6000]) < 1.04
    quality = result['processingQuality']
    assert quality['baselines'][0]['status'] == 'estimated'
    assert quality['baselines'][0]['cycles'] >= 3
    assert not any(i['reason'] in ('spike','motion') for i in quality['invalidIntervals'])


def test_spike_is_repaired_for_filtering_but_excluded_from_peaks_and_bins(client):
    clean = wave()
    values = clean.copy(); values[4500:4503] += 500
    result = apply(client, values)
    invalid = result['processingQuality']['invalidIntervals']
    assert any(i['reason'] == 'spike' and i['start'] <= 4500 < i['end'] for i in invalid)
    assert abs(result['data'][4501][1] - clean[4501]) < 10
    for event in result['peak'] + result['valley']:
        assert not any(i['start'] <= event['sequence'] < i['end'] for i in invalid)
    manager = RecordManager()
    manager.record_start_sequence, manager.record_end_sequence = 3000, 5999
    manager.raw_record_queue.extend([[i,float(y)] for i,y in enumerate(values)])
    record = manager.build_record_data(FilterConfig(**result['filter_config']),
        filtered_data=result['data'], peak_data=result['peak'], valley_data=result['valley'],
        processing_quality=result['processingQuality'],
        analysis={'basis':'amplitude','amplitudeMode':'fixed','lower':90,'upper':260})
    saved = compact_record_data(record)
    assert saved['processingQuality'] == result['processingQuality']
    assert saved['raw'][4501][1] == values[4501]
    assert saved['respiratoryBins']
    assert all(not (b['start'] < i['end'] and b['end'] > i['start'])
               for b in saved['respiratoryBins'] for i in invalid)


def test_sustained_step_does_not_create_valid_cycles_across_motion(client):
    values = wave(); values[3500:3750] += 400
    result = apply(client, values)
    invalid = result['processingQuality']['invalidIntervals']
    assert any(i['reason'] == 'motion' and i['start'] <= 3500 and i['end'] >= 3750 for i in invalid)
    assert not any(3500 <= p['sequence'] < 3750 for p in result['peak'] + result['valley'])
    assert any(p['sequence'] > 6000 for p in result['peak'])


@pytest.mark.parametrize('scenario', ['normal','tachypnea','bradypnea','shallow','deep','rapid_shallow','apnea'])
def test_clean_physiologic_variation_is_not_an_artifact(client, scenario):
    config = replace(SCENARIO_PRESETS[scenario], noise=0, artifact_chance=0)
    raw = generate_preview(config, 90, 50)
    result = apply(client, [p[1] for p in raw])
    assert not any(i['reason'] in ('spike','motion') for i in result['processingQuality']['invalidIntervals'])


def test_flat_record_reports_insufficient_baseline_evidence(client):
    result = apply(client, np.full(2000,180.0))
    assert result['processingQuality']['baselines'][0]['status'] == 'insufficient_cycles'
    assert not result['peak'] and not result['valley']


def test_sensitivity_redetection_honors_invalid_intervals(client):
    values = wave(60)
    response = client.post('/detectPeaks', json={
        'filtered_data':[[i,float(y)] for i,y in enumerate(values)],
        'invalid_intervals':[{'start':1000,'end':2000,'reason':'motion'}],
    })
    assert response.status_code == 200
    assert not any(1000 <= p['sequence'] < 2000 for p in response.json()['peak'] + response.json()['valley'])
    assert response.json()['peak']


def test_invalid_quality_interval_is_rejected(client):
    response = client.post('/detectPeaks', json={'invalid_intervals':[{'start':10,'end':5,'reason':'motion'}]})
    assert response.status_code == 422


def test_gap_is_retained_and_never_used_as_a_slow_breath(client):
    values = wave()
    raw = [[i,float(y)] for i,y in enumerate(values) if not 3500 <= i < 4000]
    result = client.post('/applyFilter',json={'raw_data':raw,'filter_config':{'processing_mode':'amplitude'}}).json()
    assert [p[0] for p in result['data']] == [p[0] for p in raw]
    assert {'start':3500,'end':4000,'reason':'gap'} in result['processingQuality']['invalidIntervals']
    assert result['metrics']['bpm'] == pytest.approx(18,abs=.1)


def test_baseline_can_still_be_disabled(client):
    result = apply(client,wave(),restore_baseline=False)
    assert abs(np.mean(np.asarray(result['data'])[3000:6000,1])) < 2
    assert result['processingQuality']['baselines'][0]['status'] == 'disabled'


def test_continuous_motion_can_yield_no_valid_bins(client):
    raw = generate_preview(SCENARIO_PRESETS['cough_artifact'],180,50)
    result = apply(client,[p[1] for p in raw])
    assert any(i['reason']=='motion' for i in result['processingQuality']['invalidIntervals'])
    # A processing result is still available for diagnosis, but raw stays intact.
    assert len(result['data']) == len(raw)
    assert result['processingQuality']['baselines'][0]['status'] == 'insufficient_cycles'


@pytest.mark.parametrize('mode', ['time', 'amplitude'])
@pytest.mark.parametrize('scenario', ['motion_artifact', 'cough_artifact'])
def test_masked_samples_are_real_reference_filter_output(client, mode, scenario):
    from scipy import signal
    from scipy.ndimage import gaussian_filter1d
    from ct_breath.breath_process.offline_quality import artifact_masks, runs

    raw = generate_preview(SCENARIO_PRESETS[scenario], 100, 50)
    values = np.array([p[1] for p in raw], dtype=float)
    result = apply(client, values, processing_mode=mode)
    quality = result['processingQuality']
    assert quality['version'] == 2
    invalid = quality['invalidIntervals']
    reference_mask = np.array([any(i['start'] <= n < i['end'] and i['reason'] in ('motion', 'too_short')
                                   for i in invalid) for n in range(len(values))])
    assert reference_mask.any()
    config = FilterConfig(**result['filter_config'])
    working = values.copy()
    spikes, _ = artifact_masks(values, 50)
    for a, b in runs(spikes):
        working[a:b] = np.interp(np.arange(a, b), [a-1, b], [working[a-1], working[b]])
    sos = signal.butter(config.order, [config.lowpass_cutoff, config.highpass_cutoff],
                        btype='bandpass', fs=50, output='sos')
    expected = gaussian_filter1d(signal.sosfiltfilt(sos, working), config.gaussian_sigma)
    expected += quality['baselines'][0]['offset']
    actual = np.array(result['data'])[:, 1]
    np.testing.assert_allclose(actual[reference_mask], np.round(expected[reference_mask], 1))
    assert np.max(np.abs(actual[reference_mask] - values[reference_mask])) > 1
    assert not any(reference_mask[p['sequence']] for p in result['peak'] + result['valley'])


def test_unreturned_abrupt_displacement_is_not_accepted_as_new_breathing_baseline(client):
    values = wave(); values[4500:] += 400
    result = apply(client,values)
    assert any(i['reason']=='motion' and i['start'] <= 4500 and i['end']==9000
               for i in result['processingQuality']['invalidIntervals'])
    assert not any(p['sequence'] >= 4500 for p in result['peak']+result['valley'])


def test_reference_filter_does_not_cross_gaps_or_invent_missing_samples(client):
    raw = [[0, 180.0], [1, 200.0], [100, 350.0]]
    raw += [[i+1000, float(v)] for i, v in enumerate(wave(30))]
    result = client.post('/applyFilter', json={'raw_data':raw,
        'filter_config':{'processing_mode':'amplitude', 'restore_baseline':False}}).json()
    assert [p[0] for p in result['data']] == [p[0] for p in raw]
    assert np.isfinite(np.array(result['data'])[:, 1]).all()
    # A one-sample segment has no oscillation; it must not borrow its neighbors.
    assert result['data'][2] == [100, 0.0]
    assert any(i['reason'] == 'too_short' and i['start'] <= 100 < i['end']
               for i in result['processingQuality']['invalidIntervals'])


def record_bins(values, result, mode):
    manager = RecordManager()
    manager.record_start_sequence, manager.record_end_sequence = 1000, len(values)-1001
    manager.raw_record_queue.extend([[i,float(v)] for i,v in enumerate(values)])
    record = manager.build_record_data(FilterConfig(**result['filter_config']),
        filtered_data=result['data'], peak_data=result['peak'], valley_data=result['valley'],
        processing_quality=result['processingQuality'],
        analysis={'basis':mode,'amplitudeMode':'fixed','lower':100,'upper':250})
    return compact_record_data(record)['respiratoryBins']


@pytest.mark.parametrize('mode', ['time','amplitude'])
def test_local_cough_preserves_normal_bins_on_both_sides(client, mode):
    clean = wave(100)
    values = clean.copy()
    values[2500:2520] += np.linspace(400,0,20)
    result = apply(client, values, processing_mode=mode)
    invalid = result['processingQuality']['invalidIntervals']
    assert any(i['reason']=='motion' and i['start']<=2500<i['end'] for i in invalid)
    bins = record_bins(values,result,mode)
    assert any(2100<b['start']<b['end']<2400 for b in bins)
    assert any(2700<b['start']<b['end']<3000 for b in bins)
    assert all(not (b['start']<i['end'] and b['end']>i['start']) for b in bins for i in invalid)
    # Away from the local exclusion, the cough must not distort the clean result.
    normal = apply(client, clean, processing_mode=mode)
    a=np.array(result['data'])[:,1]; b=np.array(normal['data'])[:,1]
    assert np.max(np.abs(a[2100:2300]-b[2100:2300])) < 3
    assert np.max(np.abs(a[2800:3000]-b[2800:3000])) < 3


@pytest.mark.parametrize('mode', ['time','amplitude'])
def test_repeated_local_coughs_do_not_discard_all_normal_breaths(client, mode):
    values = wave(100)
    for index in range(1500,4000,500):
        values[index:index+20] += np.linspace(400,0,20)
    result = apply(client, values, processing_mode=mode)
    bins = record_bins(values,result,mode)
    invalid = result['processingQuality']['invalidIntervals']
    for index in range(1500,3500,500):
        assert any(index+150 < b['start'] < b['end'] < index+400 for b in bins)
    assert all(not (b['start']<i['end'] and b['end']>i['start']) for b in bins for i in invalid)


@pytest.mark.parametrize('mode', ['time','amplitude'])
def test_dense_cough_keeps_clean_samples_without_forcing_complete_bins(client, mode):
    from ct_breath.breath_process.offline_quality import valid_runs
    raw = generate_preview(SCENARIO_PRESETS['cough_artifact'],300,50)[8000:13000]
    result = apply(client,[p[1] for p in raw],processing_mode=mode)
    valid = valid_runs(np.arange(len(raw)),result['processingQuality']['invalidIntervals'])
    # It is acceptable to have no complete peak-to-valley interval, but nearby
    # clean samples must not all be labelled too_short due to individual coughs.
    assert sum(b-a for a,b in valid) > 250
    assert not any(i['reason']=='too_short' and i['end']-i['start']>250
                   for i in result['processingQuality']['invalidIntervals'])
