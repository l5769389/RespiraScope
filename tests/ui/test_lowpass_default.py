from test_lab_workbench import ready


def test_lab_defaults_to_lowpass_and_custom_cutoff_reaches_filter(page, ui_server):
    page.goto(ui_server['ui']+'/lab/')
    ready(page)
    assert page.locator('#filterMethodInput').count() == 0
    assert page.locator('#bandLowInput').count() == 0
    assert page.locator('#bandHighInputValue').inner_text() == '2.00 Hz'
    page.locator('#bandHighInput').press('ArrowLeft')
    high=float(page.locator('#bandHighInput').get_attribute('data-hz'))
    with page.expect_response('**/applyFilter') as event:
        page.locator('#previewBtn').click()
    result=event.value.json()
    assert result['filter_config']['offline_filter']=='baseline_lowpass'
    assert result['filter_config']['lowpass_order']==4
    assert result['filter_config']['highpass_cutoff']==high
    assert result['processingQuality']['baselines'][0]['status']=='preserved'
