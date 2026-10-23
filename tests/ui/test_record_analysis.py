import json
import math


def chart_data(page):
    return page.evaluate('''() => {
      const c=echarts.getInstanceByDom(document.querySelector('#recordChart'));
      const o=c.getOption(), bins=o.series.find(s=>s.id==='record-bins');
      return {filtered:o.series[1].data, lines:bins.markLine.data,
        labels:bins.data.map(p=>p.label.formatter), zoom:o.dataZoom[0]};
    }''')


def wait_ready(page):
    page.wait_for_function("!document.querySelector('#analysis-basis').disabled")


def test_record_analysis_lifecycle_drag_export_and_rollback(page, ui_server, tmp_path):
    raw = [[i,500+100*math.sin(2*math.pi*i/200)] for i in range(9000)]
    response=page.request.post(ui_server['api']+'/applyFilter',data={
        'raw_data':raw,'filter_config':{'offline_filter':'baseline_lowpass','order':2,'gaussian_sigma':2.2},
        'record_start_sequence':3000,'record_end_sequence':6000})
    assert response.ok
    result=response.json()
    fixture=tmp_path/'record.json'
    fixture.write_text(json.dumps({'raw':raw,'filtered':result['data'],'peaks':result['peak'],
        'valleys':result['valley'],'filterConfig':result['filter_config'],
        'startSeq':3000,'endSeq':6000,'captureStartSeq':0,'captureEndSeq':8999,
        'startAt':1700000000000,'endAt':1700000060000}))
    updates=[]
    page.on('request',lambda request:updates.append(request.url) if request.url.endswith('/setRTFilterParams') else None)
    page.goto(ui_server['ui']+'/monitor/')
    page.locator('#startBtn').click()
    page.wait_for_function("!document.querySelector('#recordStartBtn').disabled")
    page.locator('#recordStartBtn').click()
    page.wait_for_function("!document.querySelector('#recordEndBtn').disabled")
    pending=[]
    page.route('**/record/end',lambda route:pending.append(route))
    page.locator('#recordEndBtn').click()
    page.locator('#recordSection').wait_for(state='visible')
    assert page.locator('#analysis-basis').is_disabled()
    assert page.locator('#saveRecordBtn').is_disabled()
    assert page.locator('#analysis-retry').is_disabled()
    assert pending
    backend_response = pending[0].fetch()
    captured = backend_response.json()['data']
    assert captured['raw'][-1][0] - captured['endSeq'] >= 1000
    pending[0].fulfill(response=backend_response)
    wait_ready(page)
    page.unroute('**/record/end')

    # Delayed local fallback filtering must also hold the analysis controls.
    page.locator('#recordStartBtn').click()
    page.wait_for_function("!document.querySelector('#recordEndBtn').disabled")
    raw_start=int(page.locator('#rawCountValue').inner_text().replace(',',''))
    page.wait_for_function("start=>Number(document.querySelector('#rawCountValue').textContent.replace(/\\D/g,''))>=start+320",arg=raw_start)
    page.route('**/record/end',lambda route:route.fulfill(status=500,body='test fallback'))
    pending=[]
    page.route('**/applyFilter',lambda route:pending.append(route))
    with page.expect_request('**/applyFilter'):
        page.locator('#recordEndBtn').click()
    assert page.locator('#analysis-basis').is_disabled()
    assert page.locator('#saveRecordBtn').is_disabled()
    assert pending
    pending[0].fulfill(response=pending[0].fetch())
    wait_ready(page)
    page.unroute('**/record/end')
    page.unroute('**/applyFilter')
    with page.expect_download() as capture_download:
        page.locator('#saveRecordBtn').click()
    captured_file = tmp_path/'local-padding.json'
    capture_download.value.save_as(captured_file)
    captured = json.loads(captured_file.read_text())
    assert captured['raw'][-1][0] - captured['endSeq'] >= 1000


    page.locator('#loadRecordInput').set_input_files(fixture)
    page.wait_for_function("document.querySelector('#recordFileValue').textContent==='record.json'")
    page.locator('#recordSection').scroll_into_view_if_needed()
    initial=chart_data(page)
    assert all(label in initial['labels'] for label in ['吸 1','吸 5','呼 1','呼 5'])
    assert len(initial['lines'])>100
    assert not page.locator('#waveChart').evaluate("el=>!!echarts.getInstanceByDom(el).getOption().series.find(s=>s.id==='record-bins')")
    page.locator('#analysis-basis').select_option('amplitude')
    wait_ready(page)
    assert '低通 ≤ 2.00 Hz' in page.locator('#analysis-status').inner_text()
    assert chart_data(page)['filtered'] == initial['filtered']
    page.locator('#analysis-amplitudeMode').select_option('fixed')
    for key,value in [('lower','450'),('upper','550')]:
        page.locator('#analysis-'+key).fill(value)
        page.locator('#analysis-'+key).press('Tab')
    page.evaluate("echarts.getInstanceByDom(document.querySelector('#recordChart')).dispatchAction({type:'dataZoom',startValue:3000,endValue:3600})")
    before=chart_data(page)
    page.locator('#recordChart').scroll_into_view_if_needed()
    rect=page.locator('#recordChart').bounding_box()
    y=page.evaluate("echarts.getInstanceByDom(document.querySelector('#recordChart')).convertToPixel({yAxisIndex:0},450)")
    page.mouse.move(rect['x']+rect['width']/2,rect['y']+y)
    page.mouse.down()
    page.mouse.move(rect['x']+rect['width']/2,rect['y']+y-30,steps=8)
    page.mouse.up()
    moved=float(page.locator('#analysis-lower').input_value())
    assert moved>450
    after=chart_data(page)
    assert after['filtered']==before['filtered']
    assert after['lines']!=before['lines']
    assert after['zoom']['start']==before['zoom']['start']
    section=page.locator('#recordSection').bounding_box()
    chart=page.locator('#recordChart').bounding_box()
    assert chart['y']+chart['height']<=section['y']+section['height']
    page.evaluate("echarts.getInstanceByDom(document.querySelector('#recordChart')).dispatchAction({type:'dataZoom',startValue:3150,endValue:3350})")
    page.locator('#recordSection').screenshot(path=str(tmp_path/'fixed-desktop.png'))
    with page.expect_download() as event:
        page.locator('#saveRecordBtn').click()
    saved=tmp_path/'saved.json'
    event.value.save_as(saved)
    payload=json.loads(saved.read_text())
    assert payload['analysis']['basis']=='amplitude'
    assert abs(payload['analysis']['lower']-moved)<0.01
    assert len(payload['raw'])==len(raw)
    assert payload['respiratoryBins']
    assert payload['filterConfig']['processing_mode']=='amplitude'
    page.locator('#loadRecordInput').set_input_files(saved)
    page.wait_for_function("document.querySelector('#recordFileValue').textContent==='saved.json'")
    assert page.locator('#analysis-amplitudeMode').input_value()=='fixed'
    assert float(page.locator('#analysis-lower').input_value())==moved
    page.locator('#analysis-basis').select_option('time')
    wait_ready(page)
    assert chart_data(page)['filtered']==initial['filtered']
    assert page.locator('#analysis-bounds').is_hidden()
    page.route('**/applyFilter',lambda route:route.fulfill(status=500,body='test error'))
    page.locator('#analysis-basis').select_option('amplitude')
    wait_ready(page)
    assert page.locator('#analysis-basis').input_value()=='amplitude'
    assert chart_data(page)['filtered']==initial['filtered']
    # Only explicit recalculation contacts the filtering endpoint.
    page.locator('#analysis-retry').click()
    wait_ready(page)
    assert '重算失败' in page.locator('#analysis-status').inner_text()
    assert chart_data(page)['filtered']==initial['filtered']
    page.unroute('**/applyFilter')
    page.locator('#analysis-retry').click()
    wait_ready(page)
    page.set_viewport_size({'width':390,'height':844})
    page.locator('#recordSection').scroll_into_view_if_needed()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.evaluate("echarts.getInstanceByDom(document.querySelector('#recordChart')).dispatchAction({type:'dataZoom',startValue:3150,endValue:3350})")
    page.locator('#recordSection').screenshot(path=str(tmp_path/'time-mobile.png'))
    assert not updates


def test_fixed_record_export_marks_outside_extrema_only_in_file(page, ui_server, tmp_path):
    points = [[i,40+(i if i<=50 else 100-i)*0.4] for i in range(101)]
    record = tmp_path/'shallow.json'
    record.write_text(json.dumps({'raw':points,'filtered':points,'peaks':[[50,60]],'valleys':[[0,40],[100,40]],
        'startSeq':0,'endSeq':100,'startAt':1700000000000,'endAt':1700000002000,
        'analysis':{'basis':'amplitude','amplitudeMode':'fixed','lower':0,'upper':100,'inhaleRising':True}}))
    page.goto(ui_server['ui']+'/monitor/')
    page.locator('#loadRecordInput').set_input_files(record)
    page.wait_for_function("document.querySelector('#recordFileValue').textContent==='shallow.json'")
    page.locator('#recordSection').scroll_into_view_if_needed()
    with page.expect_download() as event:
        page.locator('#saveRecordBtn').click()
    saved = tmp_path/'shallow-saved.json'
    event.value.save_as(saved)
    payload = json.loads(saved.read_text())
    assert payload['analysis']['lower'] == 0 and payload['analysis']['upper'] == 100
    lines = chart_data(page)['lines']
    assert [line.get('yAxis') for line in lines] == [20,40,60,80]
    assert all('xAxis' not in line for line in lines)
    assert [(g['direction'],g['bin']) for g in payload['respiratoryBins']] == [('inhale',3),('exhale',3)]
    assert all('amplitudeRange' not in p for p in payload['peaks']+payload['valleys'])
    page.locator('#loadRecordInput').set_input_files(saved)
    page.wait_for_function("document.querySelector('#recordFileValue').textContent==='shallow-saved.json'")
    assert page.locator('#analysis-lower').input_value() == '0.00'
    assert page.locator('#analysis-upper').input_value() == '100.00'
    for key,value in [('lower','45'),('upper','55')]:
        page.locator('#analysis-'+key).fill(value)
        page.locator('#analysis-'+key).press('Tab')
    with page.expect_download() as event:
        page.locator('#saveRecordBtn').click()
    outside = tmp_path/'outside.json'
    event.value.save_as(outside)
    payload = json.loads(outside.read_text())
    assert payload['analysis']['lower'] == 45 and payload['analysis']['upper'] == 55
    assert [line.get('yAxis') for line in chart_data(page)['lines']] == [47,49,51,53]
    assert len(payload['respiratoryBins']) == 10
    assert payload['peaks'][0]['amplitudeRange'] == 'above'
    assert all(p['amplitudeRange']=='below' for p in payload['valleys'])
    markers = page.locator('#recordChart').evaluate("el=>echarts.getInstanceByDom(el).getOption().series.filter(s=>['peaks','valleys'].includes(s.id)).flatMap(s=>s.data)")
    assert len(markers) == 3
    assert all(not p.get('label', {}).get('show') for p in markers)
    assert all('itemStyle' not in p for p in markers)
    page.locator('#recordSection').screenshot(path=str(tmp_path/'fixed-bins-no-warning.png'))
