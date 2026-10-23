import json
import math


def test_workbench_desktop_mobile_and_lab_controls(page, ui_server, tmp_path):
    page.set_viewport_size({'width':1536,'height':1100})
    page.goto(ui_server['ui'])
    monitor = page.frame_locator('iframe[src*="/monitor/"]')
    monitor.locator('#startBtn').click()
    points = [[i,500+100*math.sin(2*math.pi*i/200)] for i in range(1201)]
    record = tmp_path/'ui-preview.json'
    record.write_text(json.dumps({'raw':points,'filtered':points,
        'peaks':[[i,600] for i in range(50,1200,200)],
        'valleys':[[i,400] for i in range(150,1200,200)],
        'startSeq':200,'endSeq':1000,'startAt':1700000000000,'endAt':1700000016000,
        'analysis':{'basis':'amplitude','amplitudeMode':'fixed','lower':450,'upper':550,'inhaleRising':True}}))
    monitor.locator('#loadRecordInput').set_input_files(record)
    monitor.locator('#recordSection').wait_for(state='visible')
    assert monitor.locator('#recordChart').evaluate('el=>el.clientWidth>900 && el.clientHeight>=300')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(tmp_path/'workbench-desktop.png'))
    page.locator('[data-mode="lab"]').click()
    lab = page.frame_locator('iframe[src*="/lab/"]')
    lab.locator('#previewBtn').click()
    lab.locator('#chartEmpty').wait_for(state='hidden')
    assert lab.locator('.demo-card').count()>0
    page.screenshot(path=str(tmp_path/'lab-desktop.png'))
    page.set_viewport_size({'width':390,'height':844})
    assert lab.locator('body').evaluate('el=>el.scrollWidth<=innerWidth')
    assert lab.locator('#previewBtn').is_visible()
    assert lab.locator('.primary-actions').evaluate("el=>getComputedStyle(el).position==='static'")
    page.screenshot(path=str(tmp_path/'lab-mobile.png'))
    page.locator('[data-mode="monitor"]').click()
    assert monitor.locator('#scanStartBtn').is_visible()
    assert monitor.locator('#scanEndBtn').is_visible()
    assert monitor.locator('body').evaluate('el=>el.scrollWidth<=innerWidth')
    assert monitor.locator('.control-strip').evaluate("el=>getComputedStyle(el).position==='static'")
    monitor.locator('#recordSection').scroll_into_view_if_needed()
    page.screenshot(path=str(tmp_path/'workbench-mobile.png'))
    for language in ['en', 'zh']:
        page.locator('#languageSelect').select_option(language)
        assert monitor.locator('.control-strip button').evaluate_all(
            'buttons=>buttons.every(el=>el.scrollWidth<=el.clientWidth && el.scrollHeight<=el.clientHeight)')
