import json
import math

from test_record_analysis import chart_data, wait_ready
from test_offline_settings import drag_band


def test_offline_lowpass_switch_export_import_and_rollback(page, ui_server, tmp_path):
    raw = [[i,180+28*math.sin(2*math.pi*i/2250)+60*math.sin(2*math.pi*i/170)] for i in range(6000)]
    initial = page.request.post(ui_server['api']+'/applyFilter',data={
        'raw_data':raw,'filter_config':{'processing_mode':'amplitude'},
        'record_start_sequence':1500,'record_end_sequence':4500}).json()
    fixture=tmp_path/'lowpass-input.json'
    fixture.write_text(json.dumps({'version':5,'raw':raw,'filtered':initial['data'],
        'peaks':initial['peak'],'valleys':initial['valley'],'processingQuality':initial['processingQuality'],
        'filterConfig':initial['filter_config'],'filterStatus':'offline','startSeq':1500,'endSeq':4500,
        'startTime':'2026-10-22T00:00:00','endTime':'2026-10-22T00:01:00',
        'analysis':{'basis':'amplitude','amplitudeMode':'fixed','totalBins':10,'lower':120,'upper':240,'inhaleRising':True}}))
    requests=[]
    page.on('request',lambda r:requests.append(r.url))
    page.goto(ui_server['ui']+'/monitor/')
    assert page.title() and page.locator('#startBtn').is_visible()
    page.locator('#loadRecordInput').set_input_files(fixture)
    page.wait_for_function("document.querySelector('#recordFileValue').textContent==='lowpass-input.json'")
    page.locator('#recordSection').scroll_into_view_if_needed()
    before=chart_data(page)['filtered']
    page.locator('#analysis-reset').click()
    assert page.locator('#analysis-bandLow').is_hidden()
    assert chart_data(page)['filtered']==before
    assert page.locator('#saveRecordBtn').is_disabled()
    page.route('**/applyFilter',lambda route:route.fulfill(status=500,body='test failure'))
    page.locator('#analysis-retry').click()
    page.wait_for_function("document.querySelector('#analysis-status').hasAttribute('data-error')")
    assert chart_data(page)['filtered']==before
    page.unroute('**/applyFilter')
    page.locator('#analysis-retry').click()
    wait_ready(page)
    assert chart_data(page)['filtered']!=before
    assert page.locator('#analysis-lower').input_value()=='120.00'
    assert page.locator('#analysis-upper').input_value()=='240.00'
    high=drag_band(page,'bandHigh',1)
    page.locator('#analysis-retry').click()
    wait_ready(page)
    filtered=chart_data(page)['filtered']
    with page.expect_download() as event:
        page.locator('#saveRecordBtn').click()
    saved=tmp_path/'lowpass-saved.json';event.value.save_as(saved)
    data=json.loads(saved.read_text())
    assert data['filterConfig']['offline_filter']=='baseline_lowpass'
    assert data['filterConfig']['highpass_cutoff']==high
    assert data['processingQuality']['baselines'][0]['status']=='preserved'
    assert data['raw']==raw and data['respiratoryBins']
    page.locator('#loadRecordInput').set_input_files(saved)
    page.wait_for_function("document.querySelector('#recordFileValue').textContent==='lowpass-saved.json'")
    assert page.locator('#analysis-bandHigh').is_visible()
    assert chart_data(page)['filtered']==filtered
    page.locator('#recordSection').screenshot(path='/private/tmp/respirascope-lowpass-desktop.png')
    page.set_viewport_size({'width':430,'height':1000})
    assert page.locator('#analysis-bandHigh').is_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.locator('#recordSection').screenshot(path='/private/tmp/respirascope-lowpass-mobile.png')
    page.set_viewport_size({'width':1440,'height':1100})
    assert not any(url.endswith('/setRTFilterParams') for url in requests)


def test_lab_lowpass_preview_uses_selected_filter(page, ui_server):
    page.goto(ui_server['ui']+'/lab/')
    page.locator('#previewBtn:enabled').wait_for()
    assert page.locator('#bandLowInput').is_hidden()
    with page.expect_response('**/applyFilter') as event:
        page.locator('#previewBtn').click()
    result=event.value.json()
    assert result['filter_config']['offline_filter']=='baseline_lowpass'
    assert result['processingQuality']['baselines'][0]['status']=='preserved'


def test_time_filter_switch_is_explicit_and_roundtrips(page, ui_server, tmp_path):
    raw = [[i,180+12*math.sin(2*math.pi*i/2250)+60*math.sin(2*math.pi*i/100)] for i in range(6500)]
    result=page.request.post(ui_server['api']+'/applyFilter',data={
        'raw_data':raw,'filter_config':{'processing_mode':'time'},
        'record_start_sequence':1500,'record_end_sequence':4500}).json()
    fixture=tmp_path/'time-filter.json'
    fixture.write_text(json.dumps({'version':5,'raw':raw,'filtered':result['data'],
        'peaks':result['peak'],'valleys':result['valley'],'processingQuality':result['processingQuality'],
        'filterConfig':result['filter_config'],'filterStatus':'offline','startSeq':1500,'endSeq':4500,
        'startTime':'2026-10-22T00:00:00','endTime':'2026-10-22T00:01:00',
        'analysis':{'basis':'time','amplitudeMode':'fixed','totalBins':10,'lower':120,'upper':240,'inhaleRising':True}}))
    page.goto(ui_server['ui']+'/monitor/')
    page.locator('#loadRecordInput').set_input_files(fixture)
    page.wait_for_function("document.querySelector('#recordFileValue').textContent==='time-filter.json'")
    page.locator('#recordSection').scroll_into_view_if_needed()
    assert page.locator('#analysis-filterMethod').count()==0
    assert '旧版结果' in page.locator('#analysis-status').inner_text()
    assert '时间分箱 · 带通滤波' in page.locator('#analysis-status').inner_text()
    before=chart_data(page)['filtered']
    page.locator('#analysis-reset').click()
    assert page.locator('#analysis-bandLow').is_hidden()
    assert chart_data(page)['filtered']==before
    page.locator('#analysis-reset').click()  # Explicitly load the 2 Hz low-pass preset.
    with page.expect_response('**/applyFilter') as event:
        page.locator('#analysis-retry').click()
    applied=event.value.json();wait_ready(page)
    assert applied['filter_config']['processing_mode']=='time'
    assert applied['filter_config']['offline_filter']=='baseline_lowpass'
    assert applied['filter_config']['highpass_cutoff']==2
    assert applied['data'][0][0]==500  # Both bases share the same 20 s context.
    assert '时间分箱 · 保留基线低通' in page.locator('#analysis-status').inner_text()
    assert chart_data(page)['filtered']!=before
    assert page.locator('#analysis-bounds').is_hidden()
    assert chart_data(page)['lines'] and all('xAxis' in line for line in chart_data(page)['lines'])
    with page.expect_download() as event:
        page.locator('#saveRecordBtn').click()
    saved=tmp_path/'time-lowpass.json';event.value.save_as(saved)
    exported=json.loads(saved.read_text())
    assert exported['analysis']['basis']=='time'
    assert exported['filterConfig']['offline_filter']=='baseline_lowpass'
    assert exported['raw']==raw and exported['respiratoryBins']
    page.locator('#analysis-basis').select_option('amplitude');wait_ready(page)
    assert page.locator('#analysis-bandHigh').is_visible()
    page.locator('#analysis-basis').select_option('time');wait_ready(page)
    assert page.locator('#analysis-bandHigh').is_visible()
    page.locator('#loadRecordInput').set_input_files(saved)
    page.wait_for_function("document.querySelector('#recordFileValue').textContent==='time-lowpass.json'")
    assert page.locator('#analysis-basis').input_value()=='time'
    assert page.locator('#analysis-bandHigh').is_visible()
    page.locator('#recordSection').screenshot(path='/private/tmp/respirascope-time-lowpass-desktop.png')
    page.set_viewport_size({'width':430,'height':1000})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.locator('#recordSection').screenshot(path='/private/tmp/respirascope-time-lowpass-mobile.png')
    page.set_viewport_size({'width':1440,'height':1100})
