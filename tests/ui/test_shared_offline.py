from tests.support.storage import stored_bins
import json
import math
from test_record_analysis import chart_data, wait_ready


def test_switch_reuses_signal_and_preserves_custom_parameters_bounds_and_export(page, ui_server, tmp_path):
    raw = [[i,180+80*math.sin(i*2*math.pi/170)] for i in range(4000)]
    result = page.request.post(ui_server['api']+'/applyFilter', data={'raw_data':raw,
        'filter_config':{'offline_filter':'baseline_lowpass','bandpass_mode':'custom',
                         'highpass_cutoff':1.3,'gaussian_sigma':2.2},
        'record_start_sequence':1000,'record_end_sequence':2999}).json()
    source = tmp_path/'shared.json'
    source.write_text(json.dumps({'version':5,'raw':raw,'filtered':result['data'],
        'peaks':result['peak'],'valleys':result['valley'],'filterConfig':result['filter_config'],
        'processingQuality':result['processingQuality'],'startSeq':1000,'endSeq':2999,
        'analysis':{'basis':'time','amplitudeMode':'fixed','lower':130,'upper':220},
        'amplitudeFilterOverrides':{'highpass_cutoff':2,'gaussian_sigma':1}}))
    page.goto(ui_server['ui']+'/monitor/')
    page.locator('#loadRecordInput').set_input_files(source)
    page.locator('#recordSection').wait_for(state='visible')
    before = chart_data(page)['filtered']
    calls = []
    page.on('request',lambda r:calls.append(r.url) if r.url.endswith(('/applyFilter','/detectPeaks')) else None)
    for basis in ['amplitude','time','amplitude']:
        page.locator('#analysis-basis').select_option(basis)
        wait_ready(page)
        assert chart_data(page)['filtered'] == before
        assert float(page.locator('#analysis-bandHigh').get_attribute('data-hz')) == 1.3
        assert page.locator('#analysis-lower').input_value() == '130.00'
        assert page.locator('#analysis-upper').input_value() == '220.00'
    assert not calls
    # Changing the binning basis must also preserve an unapplied detection draft.
    page.locator('#analysis-sensitivity').select_option('0.15')
    page.locator('#analysis-basis').select_option('time')
    assert page.locator('#analysis-sensitivity').input_value() == '0.15'
    assert page.locator('#saveRecordBtn').is_disabled()
    assert chart_data(page)['filtered'] == before
    page.locator('#analysis-discard').click()
    page.locator('#analysis-basis').select_option('amplitude')
    assert not calls
    with page.expect_download() as download:
        page.locator('#saveRecordBtn').click()
    saved = tmp_path/'saved.json'; download.value.save_as(saved)
    payload = json.loads(saved.read_text())
    assert payload['filterConfig']['processing_mode'] == 'amplitude'
    assert payload['filterConfig']['gaussian_sigma'] == 2.2
    assert payload['processingQuality'] == result['processingQuality']
    assert stored_bins(payload)
    assert 'timeFilterOverrides' not in payload and 'amplitudeFilterOverrides' not in payload
    page.locator('#loadRecordInput').set_input_files(saved)
    page.wait_for_function("document.querySelector('#recordFileValue').textContent==='saved.json'")
    page.locator('#analysis-basis').select_option('time'); wait_ready(page)
    assert chart_data(page)['filtered'] == before
    page.locator('#recordSection').screenshot(path=str(tmp_path/'shared-time.png'))


def test_default_bounds_use_record_only_and_exclude_invalid_samples(page, ui_server):
    page.goto(ui_server['ui']+'/monitor/')
    result = page.evaluate('''async () => {
      const {defaultAmplitudeBounds}=await import('./modules/respiratory-bins.js');
      const source={startSeq:100,endSeq:199,
        filtered:Array.from({length:300},(_,i)=>[i,i<100?-1000:i>=200?10000:i-100]),
        processingQuality:{version:2,invalidIntervals:[{start:190,end:200,reason:'motion'}]}};
      return defaultAmplitudeBounds(source);
    }''')
    assert result == {'lower':4,'upper':84}


def test_pending_analysis_does_not_persist_bounds_from_temporary_curve(page, ui_server):
    page.goto(ui_server['ui']+'/monitor/')
    result=page.evaluate('''async () => {
      const {createRecordAnalysis}=await import('./modules/record-analysis.js');
      const record={analysisPending:true,startSeq:100,endSeq:199,
        filtered:Array.from({length:100},(_,i)=>[i+100,i+1000])};
      const api=createRecordAnalysis({state:{lastRecord:record}});
      const pending={...api.settings()};
      const persistedBefore=Number.isFinite(record.analysis.lower);
      record.analysisPending=false;
      record.filtered=Array.from({length:100},(_,i)=>[i+100,i]);
      record.processingQuality={version:2,invalidIntervals:[{start:190,end:200,reason:'motion'}]};
      const completed={...api.settings()};
      record.analysis.lower=12; record.analysis.upper=77;
      record.analysisPending=true;api.settings();record.analysisPending=false;
      return {pending,persistedBefore,completed,manual:{...api.settings()}};
    }''')
    assert result['pending']['lower']==1004
    assert not result['persistedBefore']
    assert (result['completed']['lower'],result['completed']['upper'])==(4,84)
    assert (result['manual']['lower'],result['manual']['upper'])==(12,77)
