import pytest


def chart_option(page):
    return page.locator('#previewChart').evaluate('el=>echarts.getInstanceByDom(el).getOption()')


def ready(page):
    page.locator('#previewBtn:enabled').wait_for()
    page.locator('#chartEmpty').wait_for(state='hidden')


@pytest.mark.parametrize('scenario', ['motion_artifact', 'cough_artifact'])
def test_artifact_preview_keeps_a_visible_filtered_reference(page, ui_server, tmp_path, scenario):
    page.goto(ui_server['ui']+'/lab/')
    ready(page)
    page.locator('#toggleDemoGridBtn').click()
    page.locator(f'[data-scenario="{scenario}"] .demo-select-action').click()
    with page.expect_response('**/applyFilter') as response:
        page.locator('#previewBtn').click()
    ready(page)
    result = response.value.json()
    option = chart_option(page)
    reference = next(s for s in option['series'] if s.get('id') == 'artifact-reference')
    assert reference['lineStyle']['type'] == 'dashed'
    assert any(p[1] is not None for p in reference['data'])
    expected = {p[0]/50:p[1] for p in result['data']}
    assert all(expected[p[0]] == p[1] for p in reference['data'] if p[1] is not None)
    page.locator('#previewChart').screenshot(path=str(tmp_path/f'{scenario}-reference.png'))


def test_lab_preview_validation_busy_error_recovery_and_lazy_examples(page, ui_server, tmp_path):
    requests = []
    page.on('request', lambda request: requests.append(request.url))
    page.goto(ui_server['ui']+'/lab/')
    ready(page)
    assert page.title() == '模拟与滤波'
    assert page.locator('#statusText').is_visible()
    assert page.locator('#bpmInput').is_visible()
    assert page.locator('#bandHighInput').is_visible()
    assert len([url for url in requests if url.endswith('/mock/preview')]) == 1
    normal = page.locator('[data-scenario="normal"]')
    normal.locator('.demo-detail-toggle').click()
    page.wait_for_function("!document.querySelector('[data-scenario=normal] .demo-load-state')")
    assert len([url for url in requests if url.endswith('/mock/preview')]) == 2
    normal.locator('.demo-detail-toggle').click()
    normal.locator('.demo-detail-toggle').click()
    assert len([url for url in requests if url.endswith('/mock/preview')]) == 2
    normal.locator('.demo-detail-toggle').click()
    initial = chart_option(page)['series'][1]['data']
    page.locator('[data-scenario="noisy"] .demo-select-action').click()
    assert page.locator('#labStatus').get_attribute('data-state') == 'pending'
    assert '正常呼吸' in page.locator('#previewSummary').inner_text()
    assert page.locator('#bandHighInputValue').inner_text() == '2.00 Hz'
    assert page.locator('#peakRatioInput').input_value() == '0.3'
    page.locator('#bandHighInput').press('ArrowLeft')
    high=float(page.locator('#bandHighInput').get_attribute('data-hz'))
    assert chart_option(page)['series'][1]['data'] == initial
    page.locator('#secondsInput').fill('')
    page.locator('#previewBtn').click()
    assert page.locator('#secondsInput').get_attribute('aria-invalid') == 'true'
    page.locator('#secondsInput').fill('30')
    pending = []
    page.route('**/applyFilter', lambda route: pending.append(route))
    page.locator('#previewBtn').click()
    page.wait_for_function("document.querySelector('#statusText').textContent.includes('滤波预览')")
    assert page.locator('#previewBtn').is_disabled()
    assert page.locator('#applyMockBtn').is_disabled()
    assert page.locator('#bpmInput').is_disabled()
    assert page.locator('.demo-select-action:enabled').count() == 0
    assert pending
    config = pending[0].request.post_data_json['filter_config']
    assert config['bandpass_mode'] == 'custom'
    assert config['highpass_cutoff'] == high
    assert config['offline_filter'] == 'baseline_lowpass'
    assert config['peak_threshold_ratio'] == .3
    assert config['lowpass_order'] == 4
    pending[0].fulfill(status=422, json={'detail':[{'loc':['body','filter_config'],'msg':'preview-test-error'}]})
    page.locator('#previewBtn:enabled').wait_for()
    assert 'preview-test-error' in page.locator('#statusText').inner_text()
    assert chart_option(page)['series'][1]['data'] == initial
    page.unroute('**/applyFilter')
    page.locator('#previewBtn').click()
    ready(page)
    assert page.locator('#statusText').inner_text() == '预览完成。'
    assert '噪声干扰 · 30 秒 · 1500 点' in page.locator('#previewSummary').inner_text()
    assert chart_option(page)['series'][1]['data'] != initial
    assert chart_option(page)['xAxis'][0]['name'] == '时间（秒）'
    assert len(chart_option(page)['dataZoom']) == 2
    # Drag the actual rendered zoom handle, then inspect the resulting visible range.
    chart = page.locator('#previewChart')
    chart.scroll_into_view_if_needed()
    box = chart.bounding_box()
    page.mouse.move(box['x']+box['width']-18, box['y']+box['height']-19)
    page.mouse.down()
    page.mouse.move(box['x']+box['width']*.65, box['y']+box['height']-19, steps=12)
    page.mouse.up()
    page.wait_for_function("echarts.getInstanceByDom(document.querySelector('#previewChart')).getOption().dataZoom[0].end < 90")
    page.mouse.move(box['x']+box['width']*.4,box['y']+box['height']*.45)
    page.screenshot(path=str(tmp_path/'lab-workbench-desktop.png'), full_page=True)


@pytest.mark.parametrize('width', [390, 820])
def test_lab_responsive_translation_and_apply_to_monitor(page, ui_server, tmp_path, width):
    page.set_viewport_size({'width':width,'height':900})
    page.goto(ui_server['ui']+'/#lab')
    lab = page.frame_locator('iframe[src*="/lab/"]')
    lab.locator('#previewBtn:enabled').wait_for()
    lab.locator('#chartEmpty').wait_for(state='hidden')
    assert lab.locator('body').evaluate('el=>el.scrollWidth<=innerWidth')
    lab.locator('#toggleDemoGridBtn').click()
    assert lab.locator('.demo-card').count() > 5
    lab.locator('[data-scenario="tachypnea"] .demo-select-action').click()
    lab.locator('#previewBtn').click()
    lab.locator('#previewBtn:enabled').wait_for()
    assert '呼吸急促' in lab.locator('#previewSummary').inner_text()
    lab.locator('#toggleDemoGridBtn').click()
    lab.locator('#previewChart').scroll_into_view_if_needed()
    page.screenshot(path=str(tmp_path/f'lab-workbench-{width}.png'))
    page.locator('#languageSelect').select_option('en')
    lab.locator('h1').filter(has_text='Simulation and Filtering').wait_for()
    assert 'Tachypnea' in lab.locator('#previewSummary').inner_text()
    assert lab.locator('body').evaluate('el=>el.scrollWidth<=innerWidth')
    assert lab.locator('.primary-actions button').evaluate_all('els=>els.every(el=>el.scrollWidth<=el.clientWidth)')
    lab.locator('#applyMockBtn').click()
    monitor = page.frame_locator('iframe[src*="/monitor/"]')
    monitor.locator('#recordStartBtn:enabled').wait_for()
    assert page.url.endswith('#monitor')
