import json
import math

from test_record_analysis import chart_data, wait_ready


def band_value(page, key):
    return float(page.locator('#analysis-' + key).get_attribute('data-hz'))


def drag_band(page, key, hz):
    """Drag the rendered native range thumb; do not mutate application state."""
    slider = page.locator('#analysis-' + key)
    assert slider.get_attribute('type') == 'range'
    slider.scroll_into_view_if_needed()
    box = slider.bounding_box()
    position = float(slider.input_value()) / 1000
    maximum = float(slider.get_attribute('data-max-hz'))
    target = math.log(hz / .01) / math.log(maximum / .01)
    x = box['x'] + 9 + (box['width'] - 18) * position
    end = box['x'] + 9 + (box['width'] - 18) * target
    y = box['y'] + box['height'] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(end, y, steps=10)
    page.mouse.up()
    value = band_value(page, key)
    assert abs(value - hz) / hz < .08
    bpm = float(page.locator('#analysis-' + key + 'Bpm').inner_text().removesuffix(' BPM'))
    assert abs(bpm - value * 60) <= .0051
    assert page.locator('#analysis-' + key + 'Value').inner_text() == f'{value:.2f} Hz'
    assert slider.get_attribute('aria-valuetext') == f'{value:.2f} Hz, {bpm:.2f} BPM'
    return value


def test_offline_band_sensitivity_persistence_and_validation(page, ui_server, tmp_path):
    raw = [[i, 500 + (100 if (i // 200) % 2 == 0 else 25) * math.sin(i * math.pi / 100)]
           for i in range(4000)]
    initial = page.request.post(ui_server['api'] + '/applyFilter', data={
        'raw_data': raw, 'filter_config': {'offline_filter':'baseline_lowpass', 'peak_threshold_ratio': .45},
    }).json()
    fixture = tmp_path / 'offline.json'
    fixture.write_text(json.dumps({
        'version': 5, 'raw': raw, 'filtered': initial['data'], 'peaks': initial['peak'],
        'valleys': initial['valley'], 'filterConfig': initial['filter_config'],
        'startSeq': 1000, 'endSeq': 3000, 'startTime': '2026-10-21T00:00:00',
        'endTime': '2026-10-21T00:00:40', 'filterStatus': 'offline',
    }))
    requests = []
    page.on('request', lambda r: requests.append(r.url))
    page.goto(ui_server['ui'] + '/monitor/')
    assert page.url.endswith('/monitor/')
    assert page.title()
    assert page.locator('#startBtn').is_visible()
    page.locator('#loadRecordInput').set_input_files(fixture)
    page.wait_for_function("document.querySelector('#recordFileValue').textContent === 'offline.json'")
    page.locator('#recordSection').scroll_into_view_if_needed()
    assert page.locator('.analysis-band-track').count() == 1
    assert page.locator('.analysis-band-track input[type=range]').count() == 1
    assert page.locator('#analysis-bandHighBpm').inner_text() == '120.00 BPM'
    assert page.locator('#analysis-sensitivity').input_value() == '0.45'
    before = chart_data(page)
    count = page.evaluate("echarts.getInstanceByDom(document.querySelector('#recordChart')).getOption().series[2].data.length")
    page.locator('#analysis-sensitivity').select_option('0.15')
    assert page.locator('#saveRecordBtn').is_disabled()
    assert page.locator('#analysis-basis').is_enabled()
    page.route('**/detectPeaks', lambda route: route.fulfill(status=500, body='test detection failure'))
    page.locator('#analysis-retry').click()
    page.wait_for_function("document.querySelector('#analysis-status').hasAttribute('data-error')")
    assert chart_data(page)['filtered'] == before['filtered']
    assert page.evaluate("echarts.getInstanceByDom(document.querySelector('#recordChart')).getOption().series[2].data.length") == count
    assert page.locator('#analysis-sensitivity').input_value() == '0.15'
    assert page.locator('#saveRecordBtn').is_disabled()
    page.unroute('**/detectPeaks')
    with page.expect_request('**/detectPeaks'):
        page.locator('#analysis-retry').click()
    wait_ready(page)
    assert chart_data(page)['filtered'] == before['filtered']
    assert page.evaluate("echarts.getInstanceByDom(document.querySelector('#recordChart')).getOption().series[2].data.length") > count
    assert not any(url.endswith('/applyFilter') for url in requests)

    # A single cutoff remains positive; editing does not mutate the committed curve.
    page.locator('#analysis-bandHigh').press('Home')
    assert band_value(page, 'bandHigh') == .01
    assert chart_data(page)['filtered'] == before['filtered']
    assert page.locator('#saveRecordBtn').is_disabled()
    high = drag_band(page, 'bandHigh', 1.5)
    with page.expect_request('**/applyFilter') as event:
        page.locator('#analysis-retry').click()
    wait_ready(page)
    assert len(event.value.post_data_json['raw_data']) == len(raw)  # Includes both padding regions.
    custom = chart_data(page)['filtered']
    assert custom != before['filtered']
    assert f'≤ {high:.2f} Hz' in page.locator('#analysis-status').inner_text()
    with page.expect_download() as event:
        page.locator('#saveRecordBtn').click()
    saved = tmp_path / 'custom.json'
    event.value.save_as(saved)
    data = json.loads(saved.read_text())
    assert data['filterConfig']['bandpass_mode'] == 'custom'
    assert data['filterConfig']['highpass_cutoff'] == high
    assert data['filterConfig']['peak_threshold_ratio'] == .15
    page.locator('#loadRecordInput').set_input_files(saved)
    page.wait_for_function("document.querySelector('#recordFileValue').textContent === 'custom.json'")
    assert page.locator('#analysis-sensitivity').input_value() == '0.15'
    assert chart_data(page)['filtered'] == custom

    # The most recently applied settings are shared across both binning bases.
    page.locator('#analysis-basis').select_option('amplitude')
    wait_ready(page)
    amplitude_high = drag_band(page, 'bandHigh', 1.2)
    page.locator('#analysis-retry').click()
    wait_ready(page)
    updated = chart_data(page)['filtered']
    assert updated != custom
    page.locator('#analysis-basis').select_option('time')
    wait_ready(page)
    assert chart_data(page)['filtered'] == updated
    with page.expect_download() as event:
        page.locator('#saveRecordBtn').click()
    modes = tmp_path / 'modes.json'
    event.value.save_as(modes)
    page.locator('#loadRecordInput').set_input_files(modes)
    page.wait_for_function("document.querySelector('#recordFileValue').textContent === 'modes.json'")
    page.locator('#analysis-basis').select_option('amplitude')
    wait_ready(page)
    assert band_value(page, 'bandHigh') == amplitude_high

    # A failed update preserves the last committed result, but keeps the draft for retry.
    committed = chart_data(page)['filtered']
    page.route('**/applyFilter', lambda route: route.fulfill(status=500, body='test failure'))
    retry_high = drag_band(page, 'bandHigh', 1.1)
    page.locator('#analysis-retry').click()
    page.wait_for_function("document.querySelector('#analysis-status').hasAttribute('data-error')")
    assert chart_data(page)['filtered'] == committed
    assert band_value(page, 'bandHigh') == retry_high
    assert page.locator('#saveRecordBtn').is_disabled()
    page.unroute('**/applyFilter')
    page.locator('#analysis-retry').click()
    wait_ready(page)
    page.locator('#analysis-reset').click()
    assert band_value(page, 'bandHigh') == 2
    assert page.locator('#analysis-bandHighBpm').inner_text() == '120.00 BPM'
    assert page.locator('#analysis-sensitivity').input_value() == '0.3'
    page.locator('#analysis-retry').click()
    wait_ready(page)
    assert not any(url.endswith('/setRTFilterParams') for url in requests)
    page.locator('#recordSection').screenshot(path=str(tmp_path / 'offline-settings-desktop.png'))
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    mobile_high = drag_band(page, 'bandHigh', 1.1)
    with page.expect_request('**/applyFilter') as applied:
        page.locator('#analysis-retry').click()
    wait_ready(page)
    assert applied.value.post_data_json['filter_config']['highpass_cutoff'] == mobile_high
    page.locator('.record-analysis').screenshot(path=str(tmp_path / 'offline-settings-mobile.png'))


def test_slider_limit_tracks_record_sampling_rate(page, ui_server, tmp_path):
    points = [[i, 500 + 100 * math.sin(i / 20)] for i in range(1000)]
    record = tmp_path / 'low-sample-rate.json'
    record.write_text(json.dumps({
        'raw': points, 'filtered': points, 'startSeq': 200, 'endSeq': 800,
        'filterConfig': {'sampling_rate': 4, 'bandpass_mode': 'custom',
                         'lowpass_cutoff': .03, 'highpass_cutoff': 1.5},
    }))
    page.goto(ui_server['ui'] + '/monitor/')
    page.locator('#loadRecordInput').set_input_files(record)
    page.locator('#recordSection').wait_for(state='visible')
    page.locator('#analysis-bandHigh').press('End')
    assert 1.99 < band_value(page, 'bandHigh') < 2
    with page.expect_request('**/applyFilter') as request:
        page.locator('#analysis-retry').click()
    wait_ready(page)
    assert request.value.post_data_json['filter_config']['highpass_cutoff'] < 2
    assert not page.locator('#analysis-status').get_attribute('data-error')


def test_older_backend_cannot_silently_reset_slider_settings(page, ui_server, tmp_path):
    points = [[i, 500 + 100 * math.sin(i / 20)] for i in range(1000)]
    initial = page.request.post(ui_server['api'] + '/applyFilter', data={'raw_data': points}).json()
    record = tmp_path / 'server-mismatch.json'
    record.write_text(json.dumps({
        'raw': points, 'filtered': initial['data'], 'peaks': initial['peak'],
        'valleys': initial['valley'], 'filterConfig': initial['filter_config'],
        'startSeq': 200, 'endSeq': 800,
    }))
    page.goto(ui_server['ui'] + '/monitor/')
    page.locator('#loadRecordInput').set_input_files(record)
    page.locator('#recordSection').wait_for(state='visible')
    before = chart_data(page)
    high = drag_band(page, 'bandHigh', 1.5)

    def old_backend(route):
        request = route.request.post_data_json
        # Reproduce the old server silently ignoring the custom-band flag.
        request['filter_config'].pop('bandpass_mode', None)
        route.fulfill(response=route.fetch(post_data=json.dumps(request)))

    page.route('**/applyFilter', old_backend)
    page.locator('#analysis-retry').click()
    page.wait_for_function("document.querySelector('#analysis-status').hasAttribute('data-error')", timeout=3000)
    assert '后端未应用' in page.locator('#analysis-status').inner_text()
    assert band_value(page, 'bandHigh') == high
    assert chart_data(page)['filtered'] == before['filtered']
    assert page.locator('#saveRecordBtn').is_disabled()
    page.unroute('**/applyFilter')
    page.locator('#analysis-retry').click()
    wait_ready(page)
    assert band_value(page, 'bandHigh') == high
    assert chart_data(page)['filtered'] != before['filtered']
