from tests.support.storage import stored_bins
import json
import math


def test_reference_styles_share_endpoints_without_bridging_missing_data(page, ui_server):
    page.goto(ui_server['ui']+'/monitor/')
    result=page.evaluate('''async()=>{
      const {splitFilteredSeries}=await import('../shared/filtered-series.js');
      const data=[[0,10],[1,11],[2,12],[3,13],[40,20],[41,21]];
      const quality={version:2,invalidIntervals:[{start:1,end:3,reason:'filter_edge'},{start:40,end:42,reason:'motion'}]};
      return {current:splitFilteredSeries(data,quality,25),legacy:splitFilteredSeries(data,{...quality,version:1},25)};
    }''')
    assert result['current']['filtered'][:4]==[[0,10],[1,None],[2,None],[3,13]]
    assert result['current']['reference'][:4]==[[0,10],[1,11],[2,12],[3,13]]
    assert result['current']['reference'][4][1] is None
    assert result['current']['reference'][5:]==[[40,20],[41,21]]
    assert result['legacy']['reference']==[]


def test_local_cough_displays_one_curve_in_record_and_saved_data(page, ui_server, tmp_path):
    raw=[[i,180+80*math.sin(2*math.pi*.3*i/50)+(300 if 900<=i<920 else 0)] for i in range(2000)]
    result=page.request.post(ui_server['api']+'/applyFilter',data={'raw_data':raw,
        'filter_config':{'offline_filter':'baseline_lowpass','highpass_cutoff':2}}).json()
    source=tmp_path/'continuous-cough.json'
    source.write_text(json.dumps({'raw':raw,'filtered':result['data'],'peaks':result['peak'],'valleys':result['valley'],
        'filterConfig':result['filter_config'],'processingQuality':result['processingQuality'],
        'startSeq':300,'endSeq':1700,'analysis':{'basis':'amplitude','amplitudeMode':'fixed','lower':100,'upper':260}}))
    page.goto(ui_server['ui']+'/monitor/')
    page.locator('#loadRecordInput').set_input_files(source)
    page.locator('#recordSection').wait_for(state='visible')
    series=page.locator('#recordChart').evaluate("el=>echarts.getInstanceByDom(el).getOption().series")
    solid=series[1]['data'];reference=next(s['data'] for s in series if s.get('id')=='artifact-reference')
    expected=dict(result['data'])
    for points in (solid,reference):
        assert all(y is None or y==expected[x] for x,y in points)
    assert any(y is not None and dict(reference).get(x)==y for x,y in solid)
    with page.expect_download() as download:
        page.locator('#saveRecordBtn').click()
    saved=tmp_path/'continuous-saved.json';download.value.save_as(saved)
    payload=json.loads(saved.read_text())
    assert payload['filtered']==result['data'] and payload['raw']==raw
    assert all(not(b['start']<iv['end'] and b['end']>iv['start']) for b in stored_bins(payload) for iv in payload['processingQuality']['invalidIntervals'])
    page.locator('#recordChart').evaluate("el=>echarts.getInstanceByDom(el).dispatchAction({type:'dataZoom',startValue:800,endValue:1000})")
    page.locator('#recordSection').screenshot(path=str(tmp_path/'continuous-cough.png'))
