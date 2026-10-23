import json
import math

from test_record_analysis import wait_ready


def test_quality_survives_import_redetection_refilter_and_export(page, ui_server, tmp_path):
    raw = [[i, 180+100*math.sin(2*math.pi*.3*i/50)+(500 if 4500 <= i < 4503 else 0)] for i in range(9000)]
    result = page.request.post(ui_server['api']+'/applyFilter',data={
        'raw_data':raw,'filter_config':{'processing_mode':'amplitude','offline_filter':'baseline_lowpass'},
    }).json()
    source = tmp_path/'quality.json'
    quality = result['processingQuality']
    source.write_text(json.dumps({'version':5,'raw':raw,'filtered':result['data'],
        'peaks':result['peak'],'valleys':result['valley'],'filterConfig':result['filter_config'],
        'processingQuality':quality,'startSeq':3000,'endSeq':5999,
        'analysis':{'basis':'amplitude','amplitudeMode':'fixed','lower':90,'upper':260}}))
    page.goto(ui_server['ui']+'/monitor/')
    page.locator('#loadRecordInput').set_input_files(source)
    page.locator('#recordSection').wait_for(state='visible')

    def save(name):
        with page.expect_download() as download:
            page.locator('#saveRecordBtn').click()
        target = tmp_path/name
        download.value.save_as(target)
        data = json.loads(target.read_text())
        assert data['processingQuality']['invalidIntervals']
        assert data['respiratoryBins']
        for b in data['respiratoryBins']:
            assert not any(b['start'] < i['end'] and b['end'] > i['start']
                           for i in data['processingQuality']['invalidIntervals'])
        assert data['raw'] == raw
        return data

    first = save('first.json')
    assert first['processingQuality'] == quality
    page.locator('#analysis-sensitivity').select_option('0.15')
    with page.expect_request('**/detectPeaks') as request:
        page.locator('#analysis-retry').click()
    wait_ready(page)
    assert request.value.post_data_json['invalid_intervals'] == quality['invalidIntervals']
    assert save('redetected.json')['processingQuality'] == quality
    page.locator('#analysis-basis').select_option('time')
    wait_ready(page)
    updated = save('time.json')
    assert updated['processingQuality'] == quality
    assert updated['filtered'] == first['filtered']
    page.locator('#analysis-basis').select_option('amplitude')
    wait_ready(page)
    amplitude = save('amplitude-context.json')
    assert amplitude['filtered'] == first['filtered']
    page.locator('#loadRecordInput').set_input_files(tmp_path/'time.json')
    page.wait_for_function("document.querySelector('#recordFileValue').textContent==='time.json'")
    assert save('roundtrip.json')['processingQuality'] == updated['processingQuality']
    page.locator('#recordSection').screenshot(path=str(tmp_path/'offline-quality.png'))


def test_fixed_bounds_ignore_masked_extremes_and_bins_do_not_bridge_them(page, ui_server):
    page.goto(ui_server['ui']+'/monitor/')
    result = page.evaluate("""async () => {
      const {defaultAmplitudeBounds,buildRespiratoryBins}=await import('/monitor/modules/respiratory-bins.js');
      const source={filtered:Array.from({length:101},(_,i)=>[i,i<=50?i:100-i]),
        valleys:[[0,0],[100,0]],peaks:[[50,50]],
        processingQuality:{version:1,invalidIntervals:[{start:40,end:61,reason:'motion'}],baselines:[]}};
      for(let i=40;i<61;i++)source.filtered[i][1]=10000;
      return {bounds:defaultAmplitudeBounds(source),bins:buildRespiratoryBins(source,{basis:'time'})};
    }""")
    assert result['bounds']['upper'] < 50
    assert result['bins'] == []


def test_motion_reference_is_visible_and_legacy_placeholders_stay_hidden(page, ui_server, tmp_path):
    raw = [[i,180+100*math.sin(2*math.pi*.3*i/50)+(400 if 3500 <= i < 3750 else 0)] for i in range(9000)]
    result = page.request.post(ui_server['api']+'/applyFilter',data={
        'raw_data':raw,'filter_config':{'processing_mode':'amplitude','offline_filter':'baseline_lowpass'},
    }).json()
    payload = {'raw':raw,'filtered':result['data'],'peaks':result['peak'],'valleys':result['valley'],
        'filterConfig':result['filter_config'],'processingQuality':result['processingQuality'],
        'startSeq':3000,'endSeq':5999,'analysis':{'basis':'amplitude','amplitudeMode':'fixed','lower':90,'upper':270}}
    source = tmp_path/'motion.json'; source.write_text(json.dumps(payload))
    page.goto(ui_server['ui']+'/monitor/')
    page.locator('#loadRecordInput').set_input_files(source)
    page.locator('#recordSection').wait_for(state='visible')
    data = page.locator('#recordChart').evaluate("el=>echarts.getInstanceByDom(el).getOption().series.map(s=>s.data)")
    assert any(p[0]==3600 and p[1] is None for p in data[1])
    assert any(p[0]==3600 and p[1] > 400 for p in data[0])
    reference = page.locator('#recordChart').evaluate("el=>echarts.getInstanceByDom(el).getOption().series.find(s=>s.id==='artifact-reference')")
    assert reference['lineStyle']['type'] == 'dashed'
    assert '不参与分箱' in reference['name']
    assert any(p[0]==3600 and p[1]==result['data'][3600][1] for p in reference['data'])
    assert result['data'][3600][1] != raw[3600][1]
    page.locator('#recordSection').screenshot(path=str(tmp_path/'motion-quality-desktop.png'))
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.locator('#recordSection').screenshot(path=str(tmp_path/'motion-quality-mobile.png'))
    payload['processingQuality']['invalidIntervals'][0]['end'] = -1
    invalid = tmp_path/'invalid-quality.json'; invalid.write_text(json.dumps(payload))
    page.locator('#loadRecordInput').set_input_files(invalid)
    page.wait_for_function("document.querySelector('#recordFileValue').textContent.includes('Invalid offline quality')")
    assert page.locator('#recordChart').evaluate("el=>echarts.getInstanceByDom(el).getOption().series[1].data") == data[1]

    # v1 values in motion intervals were raw placeholders, not filter results.
    payload['processingQuality']['invalidIntervals'][0]['end'] = result['processingQuality']['invalidIntervals'][0]['start'] + 1
    payload['processingQuality']['version'] = 1
    payload['filtered'] = raw
    legacy = tmp_path/'legacy-quality.json'; legacy.write_text(json.dumps(payload))
    page.locator('#loadRecordInput').set_input_files(legacy)
    page.wait_for_function("document.querySelector('#recordFileValue').textContent==='legacy-quality.json'")
    assert page.locator('#recordChart').evaluate("el=>echarts.getInstanceByDom(el).getOption().series.find(s=>s.id==='artifact-reference').data") == []


def test_local_cough_keeps_normal_bins_after_refilter_and_export(page, ui_server, tmp_path):
    raw = [[i,180+100*math.sin(2*math.pi*.3*i/50)
            +(400*(2520-i)/20 if 2500<=i<2520 else 0)] for i in range(5000)]
    result = page.request.post(ui_server['api']+'/applyFilter',data={
        'raw_data':raw,'filter_config':{'processing_mode':'amplitude','offline_filter':'baseline_lowpass'},
    }).json()
    source = tmp_path/'local-cough.json'
    source.write_text(json.dumps({'version':5,'raw':raw,'filtered':result['data'],
        'peaks':result['peak'],'valleys':result['valley'],'filterConfig':result['filter_config'],
        'processingQuality':result['processingQuality'],'startSeq':1000,'endSeq':3999,
        'analysis':{'basis':'amplitude','amplitudeMode':'fixed','lower':100,'upper':250}}))
    page.goto(ui_server['ui']+'/monitor/')
    page.locator('#loadRecordInput').set_input_files(source)
    page.locator('#recordSection').wait_for(state='visible')
    page.locator('#analysis-retry').click()
    wait_ready(page)
    for mode in ['amplitude','time']:
        if mode=='time':
            page.locator('#analysis-basis').select_option(mode)
            wait_ready(page)
        with page.expect_download() as download:
            page.locator('#saveRecordBtn').click()
        target=tmp_path/f'{mode}-cough.json';download.value.save_as(target)
        saved=json.loads(target.read_text());bins=saved['respiratoryBins']
        invalid=saved['processingQuality']['invalidIntervals']
        assert saved['raw']==raw
        assert any(2100<b['start']<b['end']<2400 for b in bins)
        assert any(2700<b['start']<b['end']<3000 for b in bins)
        assert all(not (b['start']<i['end'] and b['end']>i['start']) for b in bins for i in invalid)
        plotted=page.locator('#recordChart').evaluate("el=>echarts.getInstanceByDom(el).getOption().series.find(s=>s.id==='record-bins').data")
        assert plotted
        page.locator('#recordSection').screenshot(path=str(tmp_path/f'{mode}-local-cough.png'))
