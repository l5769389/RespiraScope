import json

from playwright.sync_api import expect


def load_curve(page, ui_server, tmp_path):
    points = [[i, i if i <= 50 else 100-i] for i in range(101)]
    fixture = {'version':6, 'raw':points, 'filtered':points, 'peaks':[[50,50]], 'valleys':[[0,0]],
               'startSeq':0, 'endSeq':100, 'filterStatus':'offline',
               'analysis':{'basis':'time','totalBins':10,'inhaleRising':True},
               'processingQuality':{'version':2,'baselines':[], 'invalidIntervals':[{'start':70,'end':80,'reason':'motion'}]},
               'filterConfig':{'offline_filter':'baseline_lowpass','highpass_cutoff':2,'sampling_rate':50}}
    source = tmp_path/'source.json'; source.write_text(json.dumps(fixture))
    page.goto(ui_server['ui']+'/monitor/')
    page.locator('#loadRecordInput').set_input_files(source)
    page.locator('#recordSection').wait_for(state='visible')
    return fixture


def place(page, sequence):
    page.locator('#extrema-sequence').fill(str(sequence))
    page.locator('#extrema-place').click()


def save(page, tmp_path, name):
    with page.expect_download() as download:
        page.locator('#saveRecordBtn').click()
    path = tmp_path/name; download.value.save_as(path)
    return path, json.loads(path.read_text())


def test_manual_extrema_preview_cancel_confirm_and_roundtrip(page, ui_server, tmp_path):
    original = load_curve(page, ui_server, tmp_path)
    page.locator('#extrema-edit').click(timeout=2000)
    expect(page.locator('#saveRecordBtn')).to_be_disabled()
    place(page,75)
    expect(page.locator('#extrema-message')).to_contain_text('排除')
    place(page,100)
    page.locator('#extrema-cancel').click()
    _, cancelled = save(page,tmp_path,'cancelled.json')
    assert [p['sequence'] for p in cancelled['valleys']] == [0]
    assert 'extremaEdits' not in cancelled
    page.locator('#extrema-edit').click()
    place(page,100)
    page.locator('#extrema-undo').click()
    expect(page.locator('#extrema-summary')).to_contain_text('波谷 1')
    place(page,100)
    page.locator('#extrema-confirm').click()
    saved, result = save(page,tmp_path,'edited.json')
    assert [p['sequence'] for p in result['valleys']] == [0,100]
    assert result['filtered'] == original['filtered']
    assert result['processingQuality'] == original['processingQuality']
    assert result['binningData']['excluded'] == [[70,80]]
    assert result['extremaEdits']['automatic']['valleys'] == [0]
    page.locator('#loadRecordInput').set_input_files(saved)
    page.locator('#extrema-edit').click()
    page.locator('#extrema-restore').click()
    expect(page.locator('#extrema-summary')).to_contain_text('波谷 1')
    page.locator('#extrema-confirm').click()
    _, restored = save(page,tmp_path,'restored.json')
    assert 'extremaEdits' not in restored
    assert restored['valleys'] == cancelled['valleys']


def test_chart_edit_rebins_and_keeps_filter_unchanged(page, ui_server, tmp_path):
    load_curve(page,ui_server,tmp_path)
    # Remove the mask to measure newly available exhale bins after adding an endpoint.
    source = tmp_path/'source.json'; fixture=json.loads(source.read_text())
    fixture['processingQuality']['invalidIntervals']=[]
    source.write_text(json.dumps(fixture));page.locator('#loadRecordInput').set_input_files(source)
    _, before = save(page,tmp_path,'before.json')
    assert not any(before['binningData']['bins']['exhale'])
    page.locator('#extrema-edit').click()
    place(page,100)
    chart=page.locator('#recordChart');chart.scroll_into_view_if_needed()
    def click_point(x,y):
        pixel=page.evaluate('''([x,y]) => echarts.getInstanceByDom(document.querySelector('#recordChart')).convertToPixel({gridIndex:0},[x,y])''',[x,y])
        chart.click(position={'x':pixel[0],'y':pixel[1]})
    click_point(50,50)
    place(page,49)
    expect(page.locator('#extrema-selection')).to_contain_text('49')
    page.locator('#extrema-confirm').click()
    _, after=save(page,tmp_path,'after.json')
    assert after['peaks'][0]['sequence']==49
    assert all(after['binningData']['bins']['exhale'])
    assert before['filtered']==after['filtered']
    page.locator('#extrema-edit').click()
    click_point(49,49)
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 0')
    page.locator('#extrema-undo').click()
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 1')
    page.locator('#recordSection').screenshot(path=str(tmp_path/'extrema-desktop.png'))
    page.set_viewport_size({'width':390,'height':844})
    assert page.locator('#extrema-editor').evaluate('el=>el.scrollWidth<=el.clientWidth')
    page.locator('#extrema-editor').screenshot(path=str(tmp_path/'extrema-mobile.png'))


def test_refilter_and_redetection_clear_manual_marks_only_on_success(page, ui_server, tmp_path):
    import math
    load_curve(page,ui_server,tmp_path)
    source=tmp_path/'source.json';fixture=json.loads(source.read_text())
    points=[[i,100+40*math.sin(2*math.pi*i/200)] for i in range(1000)]
    fixture.update(raw=points,filtered=points,peaks=[points[50]],valleys=[points[150]],endSeq=999)
    fixture['processingQuality']['invalidIntervals']=[]
    source.write_text(json.dumps(fixture));page.locator('#loadRecordInput').set_input_files(source)
    page.locator('#extrema-edit').click();place(page,250);page.locator('#extrema-confirm').click()
    _, edited=save(page,tmp_path,'manual.json')
    page.route('**/applyFilter',lambda route:route.fulfill(status=500,body='test failure'))
    page.locator('#analysis-retry').click()
    expect(page.locator('#analysis-state')).to_have_text('应用失败')
    _, failed=save(page,tmp_path,'failed.json')
    assert failed['extremaEdits']==edited['extremaEdits']
    assert failed['peaks']==edited['peaks']
    page.unroute('**/applyFilter')
    page.locator('#analysis-retry').click()
    expect(page.locator('#analysis-state')).to_have_text('已应用')
    _, recalculated=save(page,tmp_path,'recalculated.json')
    assert 'extremaEdits' not in recalculated
    page.locator('#extrema-edit').click();place(page,251);page.locator('#extrema-confirm').click()
    page.locator('#analysis-sensitivity').select_option('0.15')
    page.locator('#analysis-retry').click()
    expect(page.locator('#analysis-state')).to_have_text('已应用')
    _, redetected=save(page,tmp_path,'redetected.json')
    assert 'extremaEdits' not in redetected
    assert recalculated['filtered']==redetected['filtered']


def test_fixed_amplitude_edits_preserve_exclusions_and_bounds(page, ui_server, tmp_path):
    load_curve(page,ui_server,tmp_path)
    page.locator('#analysis-basis').select_option('amplitude')
    page.locator('#analysis-amplitudeMode').select_option('fixed')
    page.locator('#analysis-lower').fill('10');page.locator('#analysis-lower').press('Tab')
    page.locator('#analysis-upper').fill('40');page.locator('#analysis-upper').press('Tab')
    _, before=save(page,tmp_path,'fixed-before.json')
    page.locator('#extrema-edit').click();place(page,100)
    expect(page.locator('#analysis-bandHigh')).to_be_disabled()
    expect(page.locator('#binningDataBtn')).to_be_disabled()
    page.locator('#analysis-bandTrack').click(position={'x':20,'y':10})
    page.locator('#extrema-confirm').click()
    _, after=save(page,tmp_path,'fixed-after.json')
    assert before['filterConfig']==after['filterConfig']
    assert before['analysis']==after['analysis']
    assert after['binningData']['excluded']==[[70,80]]
    assert all(any(a<=point<b for a,b in after['binningData']['unassigned']) for point in (0,99))
