import json
import urllib.request


def test_uv_console_loads_routes_without_a_build_and_keeps_monitor_state(page, ui_server):
    page.goto(ui_server['ui'])
    page.locator('#status-backend strong').filter(has_text='正常').wait_for()
    monitor = page.frame_locator('iframe[src*="/monitor/"]')
    monitor.locator('#startBtn').wait_for()
    assert page.locator('iframe').count() == 1
    monitor.locator('#startBtn').click()
    # The button exists before the asynchronous connection has started.
    monitor.locator('#recordStartBtn:enabled').wait_for()
    page.locator('[data-mode="lab"]').click()
    page.frame_locator('iframe[src*="/lab/"]').locator('#scenarioSelect').wait_for(state='attached')
    page.locator('[data-mode="monitor"]').click()
    assert page.locator('iframe').count() == 2
    assert monitor.locator('#startBtn').is_disabled()
    page.locator('#languageSelect').select_option('en')
    page.wait_for_function("document.title === '4D Respiratory Acquisition Algorithm'")
    monitor.locator('#recordStartBtn').filter(has_text='Record Start').wait_for()
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(ui_server['folder'] / 'console-mobile.png'))


def test_disabled_mode_is_not_loaded_even_via_hash(page, ui_server):
    def runtime(route):
        response = route.fetch()
        text = response.text().replace('"monitorEnabled": true', '"monitorEnabled": false')
        route.fulfill(response=response, body=text)
    page.route('**/runtime-config.js', runtime)
    page.goto(ui_server['ui'] + '/#monitor')
    page.locator('iframe[src*="/lab/"]').wait_for()
    assert page.locator('[data-mode="monitor"]').is_hidden()
    assert page.locator('iframe[src*="/monitor/"]').count() == 0


def test_console_runtime_uses_printed_ports(ui_server):
    with urllib.request.urlopen(ui_server['ui'] + '/runtime-config.js') as response:
        text = response.read().decode()
    runtime = json.loads(text.removeprefix('window.CT_BREATH_RUNTIME_CONFIG = ').strip().removesuffix(';'))
    assert runtime['backendPort'] == int(ui_server['api'].rsplit(':', 1)[1])
    assert runtime['consolePort'] == int(ui_server['ui'].rsplit(':', 1)[1])
    assert f"Monitor: {ui_server['ui']}/#monitor" in ui_server['log'].read_text()
