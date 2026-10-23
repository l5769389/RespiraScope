import json
import math

from test_offline_settings import band_value, drag_band
from test_record_analysis import chart_data, wait_ready


def test_pending_discard_and_persistent_error_feedback(page, ui_server, tmp_path):
    points = [[i,500+100*math.sin(i*math.pi/100)] for i in range(1200)]
    initial = page.request.post(ui_server['api']+'/applyFilter',data={'raw_data':points,'filter_config':{'offline_filter':'baseline_lowpass'}}).json()
    record=tmp_path/'feedback.json'
    record.write_text(json.dumps({'raw':points,'filtered':initial['data'],'filterConfig':initial['filter_config'],
        'peaks':initial['peak'],'valleys':initial['valley'],'startSeq':200,'endSeq':1000}))
    page.goto(ui_server['ui']+'/monitor/')
    page.locator('#loadRecordInput').set_input_files(record)
    page.locator('#recordSection').wait_for(state='visible')
    before=chart_data(page)['filtered']
    assert page.locator('#analysis-state').inner_text() == '已应用'
    drag_band(page,'bandHigh',1.5)
    assert page.locator('#analysis-state').inner_text() == '待应用'
    assert page.locator('#saveRecordBtn').is_disabled()
    page.locator('#analysis-discard').click()
    assert band_value(page,'bandHigh') == 2
    assert chart_data(page)['filtered'] == before
    assert page.locator('#analysis-state').inner_text() == '已应用'
    assert page.locator('#saveRecordBtn').is_enabled()
    drag_band(page,'bandHigh',1.5)
    page.route('**/applyFilter', lambda route:route.fulfill(status=422,content_type='application/json',
        body=json.dumps({'detail':[{'loc':['body','filter_config','lowpass_cutoff'],'msg':'cutoff-test'}]})))
    page.locator('#analysis-retry').click()
    page.wait_for_function("document.querySelector('#analysis-state').textContent === '应用失败'")
    assert 'cutoff-test' in page.locator('#analysis-status').inner_text()
    page.locator('#analysis-direction').select_option('falling')
    assert 'cutoff-test' in page.locator('#analysis-status').inner_text()
    assert chart_data(page)['filtered'] == before
    page.unroute('**/applyFilter')
    pending=[]
    page.route('**/applyFilter',lambda route:pending.append(route))
    page.locator('#analysis-retry').click()
    page.wait_for_function("document.querySelector('#analysis-state').textContent === '处理中'")
    assert page.locator('#analysis-retry').is_disabled()
    assert page.locator('#analysis-discard').is_disabled()
    assert pending
    pending[0].fulfill(response=pending[0].fetch())
    wait_ready(page)
    assert page.locator('#analysis-state').inner_text() == '已应用'
    assert page.locator('#recordSection #saveRecordBtn').is_visible()
    assert page.locator('#analysis-bandHighValue').inner_text() == '1.50 Hz'
    assert page.evaluate("""() => echarts.getInstanceByDom(document.querySelector('#recordChart'))
        .getOption().series.flatMap(s => s.markArea?.data ?? []).every(([area]) => area.label.show === false)""")
    assert page.locator('.analysis-help').is_visible()
    assert page.locator('.analysis-help summary').count() == 0
    assert 'BPM = Hz × 60' in page.locator('.analysis-help').inner_text()
    for selector in ['#recordDetailBtn', '#saveRecordBtn', '#analysis-reset']:
        page.locator(selector).hover()
        page.wait_for_function("selector => getComputedStyle(document.querySelector(selector)).backgroundColor === 'rgb(240, 247, 248)'", arg=selector)
        assert page.locator(selector).evaluate("el => getComputedStyle(el).color") == 'rgb(7, 94, 104)'
    page.locator('#recordDetailBtn').click()
    assert page.locator('#recordDetailDialog').is_visible()
    page.locator('#recordDetailCloseBtn').click()
    page.locator('#recordSection').screenshot(path=str(tmp_path/'optimized-analysis-desktop.png'))
    page.set_viewport_size({'width':390,'height':844})
    assert page.locator('.analysis-help').is_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.locator('.record-analysis').screenshot(path=str(tmp_path/'optimized-analysis-mobile.png'))
