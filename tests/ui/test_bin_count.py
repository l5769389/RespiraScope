import json

import pytest

from ct_breath.breath_process.record_manager import RecordManager
from ct_breath.http.schemas import FilterConfig
from test_record_analysis import chart_data


@pytest.mark.parametrize('basis,mode', [('time','free'), ('amplitude','free'), ('amplitude','fixed')])
def test_bin_count_updates_chart_and_roundtrips_without_refilter(page, ui_server, tmp_path, basis, mode):
    points = [[i, i if i <= 50 else 100-i] for i in range(101)]
    config = FilterConfig(processing_mode=basis)
    analysis = {'basis':basis,'amplitudeMode':mode,'lower':10,'upper':40,'inhaleRising':False}
    source = tmp_path/'old-record.json'
    source.write_text(json.dumps({'version':5,'raw':points,'filtered':points,'peaks':[[50,50]],
        'valleys':[[0,0],[100,0]],'startSeq':0,'endSeq':100,'filterConfig':config.model_dump(),'analysis':analysis}))
    page.goto(ui_server['ui']+'/monitor/')
    page.locator('#loadRecordInput').set_input_files(source)
    page.locator('#recordSection').wait_for(state='visible')
    assert page.locator('#analysis-totalBins').input_value() == '10'
    original = chart_data(page)['filtered']
    requests = []
    page.on('request', lambda request: requests.append(request.url))
    manager = RecordManager()
    manager.record_start_sequence, manager.record_end_sequence = 0, 100
    for total in [4,6,8,10,12,16,20]:
        page.locator('#analysis-totalBins').select_option(str(total))
        assert chart_data(page)['filtered'] == original
        assert f'吸气 {total//2} 箱 / 呼气 {total//2} 箱' in page.locator('#analysis-status').inner_text()
        series = page.locator('#recordChart').evaluate("el => echarts.getInstanceByDom(el).getOption().series.find(s=>s.id==='record-bins')")
        assert len(series['data']) == total
        if basis == 'amplitude' and mode == 'fixed':
            edges = [line['yAxis'] for line in series['markLine']['data']]
            assert edges == pytest.approx([10+30*i/(total//2) for i in range(1,total//2)])
        with page.expect_download() as download:
            page.locator('#saveRecordBtn').click()
        saved = tmp_path/f'{total}-bins.json'
        download.value.save_as(saved)
        exported = json.loads(saved.read_text())
        assert exported['analysis']['totalBins'] == total
        expected = manager.build_record_data(config, filtered_data=points, peak_data=[[50,50]],
            valley_data=[[0,0],[100,0]], analysis={**analysis,'totalBins':total})['respiratoryBins']
        assert len(exported['respiratoryBins']) == len(expected)
        for actual, wanted in zip(exported['respiratoryBins'], expected):
            assert actual['direction'] == wanted['direction']
            assert actual['bin'] == wanted['bin']
            assert actual['start'] == pytest.approx(wanted['start'])
            assert actual['end'] == pytest.approx(wanted['end'])
    assert not any(url.endswith(('/applyFilter','/detectPeaks')) for url in requests)
    page.locator('#loadRecordInput').set_input_files(saved)
    page.wait_for_function("document.querySelector('#recordFileValue').textContent === '20-bins.json'")
    assert page.locator('#analysis-totalBins').input_value() == '20'
    assert chart_data(page)['filtered'] == original
