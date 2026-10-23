import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from ct_breath.breath_process.record_manager import RecordManager
from ct_breath.http.schemas import FilterConfig


@pytest.mark.parametrize('legacy', [True, False])
def test_record_migration_and_roundtrip_preserve_data(page, ui_server, tmp_path, legacy):
    manager = RecordManager()
    manager.record_start_time, manager.record_end_time = 1700000000.123456, 1700000002.654321
    manager.record_start_sequence, manager.record_end_sequence = 10, 90
    points = [[i, i if i <= 50 else 100-i] for i in range(101)]
    manager.raw_record_queue.extend({'sequence':i,'value':v,'timestamp':1700000000+i*.02} for i,v in points)
    manager.scans = [{'index':1,'start_sequence':20,'end_sequence':80,
                     'start_time':1700000000.4,'end_time':1700000001.6,'auto_closed':False}]
    kwargs = dict(filtered_data=points, peak_data=[[50,50]], valley_data=[[0,0],[100,0]],
                  filter_status='offline', analysis={'basis':'amplitude','amplitudeMode':'fixed',
                  'lower':10,'upper':40,'inhaleRising':False})
    config = FilterConfig(processing_mode='amplitude')
    original = manager.build_record_data(config, **kwargs)
    if legacy:
        original['filter_params']['moving_avg_window'] = 7
        source = tmp_path/'legacy.json'
        source.write_text(json.dumps(original))
    else:
        with ThreadPoolExecutor(max_workers=1) as executor:
            source = executor.submit(lambda: asyncio.run(manager.save_record(config, str(tmp_path), **kwargs))).result()
    page.goto(ui_server['ui']+'/monitor/')
    page.locator('#loadRecordInput').set_input_files(source)
    page.locator('#recordSection').wait_for(state='visible')
    before = page.locator('#recordChart').evaluate("el=>echarts.getInstanceByDom(el).getOption().series[1].data")
    summary = {key:page.locator('#'+key).inner_text() for key in ['recordIndexRange','recordScanRange','recordPointCount','recordTimeRange']}
    with page.expect_download() as download:
        page.locator('#saveRecordBtn').click()
    saved = tmp_path/'compact.json'
    download.value.save_as(saved)
    payload = json.loads(saved.read_text())
    assert payload['version'] == 5
    assert len(saved.read_bytes()) < len(json.dumps(original, indent=2).encode()) * .5
    assert [p[:2] for p in payload['raw']] == points
    assert [p[2] for p in payload['raw']] == [p['timestamp'] for p in original['raw_data']]
    assert payload['filtered'] == points
    assert payload['startTime'] == original['record_time']['start_time']
    assert payload['endTime'] == original['record_time']['end_time']
    assert payload['startSeq'] == 10 and payload['endSeq'] == 90
    assert payload['scans'] == [{'index':1,'startSeq':20,'endSeq':80,
                               'startTime':original['scans'][0]['start_time'],
                               'endTime':original['scans'][0]['end_time']}]
    assert payload['respiratoryBins'] == original['respiratoryBins']
    assert payload['peaks'] == [{'sequence':50,'value':50,'amplitudeRange':'above'}]
    assert 'binning' not in payload and 'metrics' not in payload
    assert 'moving_avg_window' not in payload['filterConfig']
    assert 'moving_avg_window' not in payload.get('timeFilterOverrides', {})
    page.locator('#loadRecordInput').set_input_files(saved)
    page.wait_for_function("document.querySelector('#recordFileValue').textContent==='compact.json'")
    assert page.locator('#analysis-direction').input_value() == 'falling'
    assert page.locator('#analysis-lower').input_value() == '10.00'
    assert page.locator('#analysis-upper').input_value() == '40.00'
    assert page.locator('#recordChart').evaluate("el=>echarts.getInstanceByDom(el).getOption().series[1].data") == before
    assert {key:page.locator('#'+key).inner_text() for key in summary} == summary
    with page.expect_download() as download:
        page.locator('#saveRecordBtn').click()
    second = tmp_path/'roundtrip.json'
    download.value.save_as(second)
    assert json.loads(second.read_text()) == payload
