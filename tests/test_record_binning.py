import asyncio
import json
import pytest

from ct_breath.breath_process.record_manager import RecordManager
from ct_breath.http.schemas import FilterConfig


@pytest.mark.parametrize('total', [4, 6, 8, 10, 12, 16, 20])
@pytest.mark.parametrize('basis,mode', [('time','free'), ('amplitude','free'), ('amplitude','fixed')])
def test_configurable_bins_preserve_full_cycle_and_metadata(total, basis, mode):
    manager = RecordManager()
    manager.record_start_sequence, manager.record_end_sequence = 0, 100
    points = [[i, i if i <= 50 else 100-i] for i in range(101)]
    payload = manager.build_record_data(FilterConfig(), filtered_data=points,
        peak_data=[[50,50]], valley_data=[[0,0],[100,0]],
        analysis={'basis':basis,'amplitudeMode':mode,'lower':0,'upper':50,'totalBins':total})
    bins = payload['respiratoryBins']
    assert len(bins) == total
    assert [b['bin'] for b in bins] == list(range(1,total//2+1))*2
    assert bins[0]['start'] == 0 and bins[-1]['end'] == 100
    assert all(a['end'] == pytest.approx(b['start']) for a,b in zip(bins,bins[1:]))
    assert payload['analysis']['totalBins'] == total
    assert payload['binning']['totalBins'] == total
    assert len(payload['binning']['groups']) == total
    if basis == 'amplitude' and mode == 'fixed':
        assert len(payload['binning']['amplitudeEdges']) == total//2+1


def test_saved_record_contains_bins_bounds_and_extremum_flags(tmp_path):
    manager=RecordManager(pre_points=0,post_points=0)
    manager.record_start_time=1700000000
    manager.record_end_time=1700000002
    manager.record_start_sequence=0
    manager.record_end_sequence=100
    points=[[i, i if i<=50 else 100-i] for i in range(101)]
    manager.raw_record_queue.extend(points)
    manager.filter_record_queue.extend(points)
    manager.peak_record_queue.append([50,50])
    manager.valley_record_queue.extend([[0,0],[100,0]])
    options={'basis':'amplitude','amplitudeMode':'fixed','lower':10,'upper':40,'inhaleRising':True}
    saved=asyncio.run(manager.save_record(FilterConfig(),str(tmp_path),analysis=options))
    payload=json.loads(open(saved).read())
    assert payload['version'] == 5
    assert 'binning' not in payload and 'raw_data' not in payload
    assert payload['raw'] == points
    assert len(payload['respiratoryBins'])==10
    assert payload['respiratoryBins'][0]['start']==10
    assert payload['respiratoryBins'][-1]['end']==90
    assert payload['peaks'][0] == {'sequence':50,'value':50,'amplitudeRange':'above'}
    assert all(p['amplitudeRange']=='below' for p in payload['valleys'])
    assert payload['analysis']['lower']==10


def test_default_record_saves_time_bins_without_amplitude_range_flags():
    manager=RecordManager()
    manager.record_start_sequence=0
    manager.record_end_sequence=100
    points=[[i, i if i<=50 else 100-i] for i in range(101)]
    payload=manager.build_record_data(FilterConfig(),filtered_data=points,peak_data=[[50,50]],valley_data=[[0,0],[100,0]])
    assert len(payload['respiratoryBins'])==10
    assert payload['binning']['amplitudeBounds'] is None
    assert payload['peak'][0]['outOfRange'] is None


def test_shallow_fixed_breath_keeps_empty_bins_and_inclusive_extrema():
    manager = RecordManager()
    manager.record_start_sequence, manager.record_end_sequence = 0, 100
    points = [[i, 40 + (i if i <= 50 else 100-i) * 0.4] for i in range(101)]
    payload = manager.build_record_data(FilterConfig(), filtered_data=points,
        peak_data=[[50, 60]], valley_data=[[0, 40], [100, 40]],
        analysis={'basis':'amplitude', 'amplitudeMode':'fixed', 'lower':0, 'upper':100})
    groups = payload['binning']['groups']
    assert len(groups) == 10
    assert [(g['direction'], g['bin']) for g in groups if g['intervals']] == [('inhale',3), ('exhale',3)]
    assert all(p['outOfRange'] is False for p in payload['peak'] + payload['valley'])
    assert len(payload['respiratoryBins']) == 2


def test_bins_are_clipped_to_record_and_follow_reversed_sensor():
    manager = RecordManager()
    manager.record_start_sequence, manager.record_end_sequence = 20, 80
    points = [[i, i if i <= 50 else 100-i] for i in range(101)]
    payload = manager.build_record_data(FilterConfig(), filtered_data=points,
        peak_data=[[50,50]], valley_data=[[0,0],[100,0]],
        analysis={'basis':'amplitude', 'amplitudeMode':'fixed', 'lower':0, 'upper':50, 'inhaleRising':False})
    assert [(b['direction'],b['bin']) for b in payload['respiratoryBins']] == [
        ('exhale',3),('exhale',4),('exhale',5),('inhale',1),('inhale',2),('inhale',3)]
    assert payload['respiratoryBins'][0]['start'] == 20
    assert payload['respiratoryBins'][-1]['end'] == 80
    assert all(p['outOfRange'] is False for p in payload['peak']+payload['valley'])


def test_save_api_uses_analysis_and_offline_signal_without_changing_live_filter(tmp_path):
    import math
    from fastapi.testclient import TestClient
    from ct_breath.app import create_app
    from ct_breath.config import AppConfig
    app = create_app(AppConfig(enable_mock_signal=True, enable_front_console=False, record_storage_root=tmp_path))
    system = app.state.session_manager.get_system('save-bins')
    manager = system.record_manager
    manager.record_start_time, manager.record_end_time = 1700000000, 1700000020
    manager.record_start_sequence, manager.record_end_sequence = 300, 1300
    manager.raw_record_queue.extend([[i, 500+100*math.sin(i*math.pi/100)] for i in range(1800)])
    # Stale realtime points must not be exported as the selected offline result.
    manager.filter_record_queue.extend([[i, 0] for i in range(1800)])
    client = TestClient(app)
    options = {'basis':'amplitude','amplitudeMode':'fixed','lower':450,'upper':550,'inhaleRising':True,'totalBins':16}
    response = client.post('/record/save', headers={'X-RespiraScope-Session':'save-bins'}, json={'analysis':options})
    assert response.status_code == 200, response.text
    payload = json.loads(open(response.json()['data']['file_path']).read())
    assert payload['analysis'] == options
    assert payload['version'] == 5
    assert payload['respiratoryBins']
    assert all(300 <= b['start'] < b['end'] <= 1300 for b in payload['respiratoryBins'])
    assert payload['filterConfig']['processing_mode'] == 'amplitude'
    assert payload['filterConfig']['offline_filter'] == 'baseline_lowpass'
    assert payload['filterConfig']['highpass_cutoff'] == 2
    assert payload['filterStatus'] == 'offline'
    invalid = payload['processingQuality']['invalidIntervals']
    assert payload['processingQuality']['baselines']
    assert all(not (b['start'] < i['end'] and b['end'] > i['start'])
               for b in payload['respiratoryBins'] for i in invalid)
    assert 'timeFilterOverrides' not in payload
    assert max(p[1] for p in payload['filtered']) > 550
    assert system.signal_processor.filter_config.processing_mode == 'time'
    for invalid in [{'lower':550,'upper':450}, {'lower':None}, {'basis':'unknown'}, {'totalBins':9}, {'totalBins':0}, {'totalBins':22}]:
        response = client.post('/record/save', json={'analysis':{**options, **invalid}})
        assert response.status_code == 422
