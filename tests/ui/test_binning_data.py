import json

from ct_breath.binning.data import build_binning_data, build_binning_timeline
from ct_breath.binning.respiratory import build_respiratory_bins
from test_record_analysis import wait_ready


def test_binning_details_match_export_and_backend(page, ui_server, tmp_path):
    errors=[]
    page.on('pageerror', lambda error: errors.append(str(error)))
    points=[[i,i if i<=50 else 100-i] for i in range(101)]
    quality={'version':2,'baselines':[], 'invalidIntervals':[{'start':70,'end':80,'reason':'motion'}]}
    options={'basis':'amplitude','amplitudeMode':'fixed','lower':10,'upper':40,'inhaleRising':True,'totalBins':10}
    fixture={'version':5,'raw':points,'filtered':points,'peaks':[[50,50]],'valleys':[[0,0],[100,0]],
             'processingQuality':quality,'analysis':options,'startSeq':0,'endSeq':100,'filterStatus':'offline',
             'filterConfig':{'offline_filter':'baseline_lowpass','highpass_cutoff':2,'sampling_rate':50},
             'binningData':{'version':3,'inhaleRising':True,'bins':{'inhale':[[]]*5,'exhale':[[]]*5},'excluded':{'motion':[[0,100]]},'unassigned':{}}}
    source=tmp_path/'binning.json';source.write_text(json.dumps(fixture))
    page.goto(ui_server['ui']+'/monitor/')
    page.locator('#loadRecordInput').set_input_files(source)
    page.locator('#recordSection').wait_for(state='visible')
    page.locator('#binningDataBtn').click()
    assert page.locator('#binningDataDialog').is_visible()
    assert page.locator('.binning-data-summary article').count()==3
    page.locator('#binningStatusFilter').select_option('excluded')
    assert page.locator('#binningDataRows tr').count()==1
    assert '排除' in page.locator('#binningDataRows').inner_text()
    page.locator('#binningJsonTab').click()
    visible=json.loads(page.locator('#binningDataJson').inner_text())
    assert set(visible)=={'version','inhaleRising','bins','excluded','unassigned'} and visible['version']==4
    assert set(visible['bins'])=={'inhale','exhale'}
    assert len(visible['bins']['inhale'])==len(visible['bins']['exhale'])==5
    assert visible['inhaleRising'] is True
    assert visible['excluded']==[[70,80]]
    assert isinstance(visible['unassigned'],list) and visible['unassigned']
    assert page.locator('#binningDataHead th').count()==4
    assert page.locator('#binningReasonLegend').count()==0
    assert '原因' not in page.locator('#binningDataDialog').inner_text()
    assert 'motion' not in page.locator('#binningDataJson').inner_text()
    page.locator('#binningDataDialog').screenshot(path=str(tmp_path/'binning-json.png'))
    data=[dict(sequence=x,value=y) for x,y in points]
    bins=build_respiratory_bins(data,[data[50]],[data[0],data[100]],options,invalid_intervals=quality['invalidIntervals'])
    assert visible==build_binning_data(points,bins,quality['invalidIntervals'],options,0,100)
    with page.expect_download() as download:
        page.locator('#binningDataDownload').click()
    exported=tmp_path/'details.json';download.value.save_as(exported)
    assert json.loads(exported.read_text())==visible
    page.locator('#binningTableTab').click()
    page.locator('#binningStatusFilter').select_option('all')
    page.locator('#binningDataDialog').screenshot(path=str(tmp_path/'binning-desktop.png'))
    page.set_viewport_size({'width':390,'height':844})
    assert page.locator('#binningDataDialog').evaluate('el=>el.scrollWidth<=el.clientWidth')
    page.locator('#binningDataDialog').screenshot(path=str(tmp_path/'binning-mobile.png'))
    page.keyboard.press('Escape')
    assert not page.locator('#binningDataDialog').is_visible()
    with page.expect_download() as download:
        page.locator('#saveRecordBtn').click()
    saved=tmp_path/'record.json';download.value.save_as(saved)
    assert json.loads(saved.read_text())['binningData']==visible
    page.locator('#loadRecordInput').set_input_files(saved)
    page.locator('#binningDataBtn').click();page.locator('#binningJsonTab').click()
    assert json.loads(page.locator('#binningDataJson').inner_text())==visible
    page.keyboard.press('Escape')
    # Changed settings rebuild the timeline instead of reusing the stored snapshot.
    page.locator('#analysis-basis').select_option('time');wait_ready(page)
    page.locator('#binningDataBtn').click();page.locator('#binningJsonTab').click()
    changed=json.loads(page.locator('#binningDataJson').inner_text())
    assert changed != visible
    assert isinstance(changed['unassigned'],list)
    assert all(len(interval)==2 for interval in changed['unassigned'])
    page.keyboard.press('Escape')
    page.locator('#analysis-direction').select_option('falling');wait_ready(page)
    page.locator('#binningDataBtn').click();page.locator('#binningJsonTab').click()
    reversed_data=json.loads(page.locator('#binningDataJson').inner_text())
    assert reversed_data['inhaleRising'] is False
    assert reversed_data['bins']['inhale']==changed['bins']['exhale']
    assert reversed_data['bins']['exhale']==changed['bins']['inhale']
    assert '下降' in page.locator('#binningJsonHelp').inner_text()
    assert reversed_data['excluded']==changed['excluded']
    assert reversed_data['unassigned']==changed['unassigned']
    assert not errors


def test_browser_merges_status_ranges_like_backend(page, ui_server):
    page.goto(ui_server['ui']+'/monitor/')
    cases = [
        {'filtered':[[i,i] for i in range(12)],
         'bins':[{'start':0,'end':2,'direction':'exhale','bin':1}],
         'invalid':[{'start':3,'end':7,'reason':'motion'},
                    {'start':5,'end':9,'reason':'filter_edge'}],
         'options':{'basis':'time','totalBins':4,'inhaleRising':False}, 'start':0,'end':11},
        {'filtered':[[i,i] for i in range(21)], 'bins':[], 'invalid':[],
         'options':{'basis':'amplitude','amplitudeMode':'fixed','lower':5,'upper':15},
         'start':0,'end':30},
    ]
    for case in cases:
        actual=page.evaluate('''async c=>{
          const {buildBinningTimeline,compactBinningData}=await import('./modules/binning-data.js');
          const timeline=buildBinningTimeline(c.filtered,c.bins,c.invalid,c.options,c.start,c.end);
          return {timeline,data:compactBinningData(c.filtered,timeline)};
        }''',case)
        assert actual['timeline']==build_binning_timeline(**case)
        assert actual['data']==build_binning_data(**case)
