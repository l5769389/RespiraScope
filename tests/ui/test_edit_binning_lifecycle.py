"""Exercise actual editor controls, preview, classification and record persistence."""
import json

import pytest
from playwright.sync_api import expect
from test_extrema_editor import place, save


@pytest.mark.parametrize('basis,amplitude_mode', [('time','free'),('amplitude','free'),('amplitude','fixed')])
@pytest.mark.parametrize('rising', [True,False])
def test_edit_undo_cancel_restore_and_export_are_consistent(page,ui_server,tmp_path,basis,amplitude_mode,rising):
    points=[[i,50-abs(i%100-50)] for i in range(201)]
    fixture={'version':6,'raw':points,'filtered':points,'peaks':[points[50],points[150]],
             'valleys':[points[0],points[100],points[200]],'startSeq':0,'endSeq':200,
             'filterStatus':'offline','analysis':{'basis':basis,'amplitudeMode':amplitude_mode,
                'lower':0,'upper':50,'totalBins':12,'inhaleRising':rising},
             'filterConfig':{'offline_filter':'baseline_lowpass','highpass_cutoff':2,'sampling_rate':50}}
    path=tmp_path/'complete.json';path.write_text(json.dumps(fixture))
    page.goto(ui_server['ui']+'/monitor/')
    page.locator('#loadRecordInput').set_input_files(path)
    _,baseline=save(page,tmp_path,'baseline.json')
    assert baseline['binningData']['unassigned']==[]
    for groups in baseline['binningData']['bins'].values():
        assert len(groups)==6 and all(len(intervals)==2 for intervals in groups)

    def delete_pair():
        for sequence in [50,100]:
            place(page,sequence)
            page.keyboard.press('Delete')
        preview=page.locator('#recordChart').evaluate(
            "el=>echarts.getInstanceByDom(el).getOption().series.find(s=>s.id==='record-bins').data")
        assert len(preview)==6
        assert all(150<item['value'][0]<200 for item in preview)
        assert all(item['label']['formatter'].startswith('呼 ' if rising else '吸 ') for item in preview)

    page.locator('#extrema-edit').click()
    delete_pair()
    expect(page.locator('#saveRecordBtn')).to_be_disabled()
    expect(page.locator('#binningDataBtn')).to_be_disabled()
    # Undo the valley deletion; the missing peak can again be recovered from
    # two valley anchors. Undo once more to restore the original marker arrays.
    page.locator('#extrema-undo').click()
    page.locator('#extrema-undo').click()
    page.locator('#extrema-confirm').click()
    _,undone=save(page,tmp_path,'undone.json')
    assert undone['binningData']==baseline['binningData']
    assert undone['peaks']==baseline['peaks'] and undone['valleys']==baseline['valleys']
    assert 'extremaEdits' not in undone

    page.locator('#extrema-edit').click();delete_pair()
    page.locator('#extrema-cancel').click()
    _,cancelled=save(page,tmp_path,'cancelled.json')
    assert cancelled['binningData']==baseline['binningData']
    assert cancelled['peaks']==baseline['peaks'] and cancelled['valleys']==baseline['valleys']

    page.locator('#extrema-edit').click();delete_pair()
    page.locator('#extrema-confirm').click()
    saved,edited=save(page,tmp_path,'edited.json')
    assert edited['filtered']==baseline['filtered'] and edited['raw']==baseline['raw']
    assert edited['binningData']['unassigned']==[[0,150]]
    assert edited['binningData']['excluded']=={'quality':[],'range':[]}
    last_direction='exhale' if rising else 'inhale'
    assert all(edited['binningData']['bins'][last_direction])
    assert not any(edited['binningData']['bins']['inhale' if rising else 'exhale'])
    page.locator('#binningDataBtn').click();page.locator('#binningJsonTab').click()
    assert json.loads(page.locator('#binningDataJson').inner_text())==edited['binningData']
    page.keyboard.press('Escape')
    page.locator('#loadRecordInput').set_input_files(saved)
    _,reloaded=save(page,tmp_path,'reloaded.json')
    assert reloaded['binningData']==edited['binningData']
    assert reloaded['extremaEdits']==edited['extremaEdits']
    page.locator('#extrema-edit').click();page.locator('#extrema-restore').click()
    page.locator('#extrema-confirm').click()
    _,restored=save(page,tmp_path,'restored.json')
    assert restored['binningData']==baseline['binningData']
    assert restored['peaks']==baseline['peaks'] and restored['valleys']==baseline['valleys']
    assert 'extremaEdits' not in restored


def test_edit_binning_frontend_backend_parity_with_masks_and_buffers(page,ui_server):
    from ct_breath.binning.data import build_binning_data
    from ct_breath.binning.respiratory import build_respiratory_bins
    points=[[1000+2*i,50-abs(i%100-50)] for i in range(201)]
    page.goto(ui_server['ui']+'/monitor/')
    cases=[]
    for mode in ['time','free','fixed']:
        for retained in [[0,50,100,150,200],[0,150,200],[50,150],[]]:
            options={'basis':'time' if mode=='time' else 'amplitude','amplitudeMode':mode,
                     'lower':10,'upper':40,'totalBins':16,'inhaleRising':False}
            source={'filtered':points,'peaks':[points[i] for i in retained if i in [50,150]],
                    'valleys':[points[i] for i in retained if i in [0,100,200]],
                    'processingQuality':{'invalidIntervals':[{'start':1070,'end':1120},{'start':1100,'end':1130}]}}
            cases.append({'source':source,'options':options})
    actual=page.evaluate('''async cases=>{
      const {buildRespiratoryBins}=await import('./modules/respiratory-bins.js');
      const {buildBinningTimeline,compactBinningData}=await import('./modules/binning-data.js');
      return cases.map(({source,options})=>{
        const invalid=source.processingQuality.invalidIntervals;
        const bins=buildRespiratoryBins(source,options);
        return compactBinningData(source.filtered,buildBinningTimeline(source.filtered,bins,invalid,options,1021,1381));
      });
    }''',cases)
    for case,got in zip(cases,actual):
        source,options=case['source'],case['options']
        data=lambda key:[dict(sequence=x,value=y) for x,y in source[key]]
        invalid=source['processingQuality']['invalidIntervals']
        bins=build_respiratory_bins(data('filtered'),data('peaks'),data('valleys'),options,invalid_intervals=invalid)
        expected=build_binning_data(points,bins,invalid,options,1021,1381)
        assert got==expected
        assert got['excluded']['quality']==[[35,65]]
        all_groups=[*got['bins']['inhale'],*got['bins']['exhale'],*got['excluded'].values(),got['unassigned']]
        assert sorted(i for group in all_groups for a,b in group for i in range(a,b))==list(range(11,191))
