"""Browser checks run with: uv run --group ui-test pytest tests/ui."""
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import closing

import pytest


@pytest.fixture(scope='session')
def ui_server(tmp_path_factory):
    pytest.importorskip('playwright.sync_api')
    folder = tmp_path_factory.mktemp('ui-server')
    with closing(socket.create_server(('127.0.0.1', 0))) as listener:
        port = listener.getsockname()[1]
    config = folder / 'breath.toml'
    # Equal configured ports exercise backend/UI port collision handling.
    config.write_text(f'''[backend]
host = "127.0.0.1"
port = {port}
[console]
host = "127.0.0.1"
port = {port}
[mock]
enabled = true
bind_host = "127.0.0.1"
[sensor]
port = 0
[record]
storage_root = "{folder.as_posix()}/records"
''')
    log = folder / 'startup.log'
    with log.open('w') as output:
        process = subprocess.Popen([sys.executable, '-m', 'ct_breath', '--no-browser', '--config', str(config)],
                                   cwd=folder, stdout=output, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            text = log.read_text()
            api_match = re.search(r'Backend API: (http://\S+)', text)
            ui_match = re.search(r'Open Console: (http://\S+)', text)
            if process.poll() is not None:
                pytest.fail(text)
            if api_match and ui_match:
                api, ui = api_match[1], ui_match[1]
                try:
                    with urllib.request.urlopen(f'{api}/health', timeout=0.5) as response:
                        assert response.status == 200
                    break
                except OSError:
                    pass
            time.sleep(0.05)
        else:
            pytest.fail(f'Startup timed out: {log.read_text()}')
        assert api != ui
        yield {'api': api, 'ui': ui, 'log': log, 'folder': folder, 'config': config}
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


@pytest.fixture(scope='session')
def browser():
    playwright = pytest.importorskip('playwright.sync_api')
    with playwright.sync_playwright() as driver:
        options = {'headless': True}
        if channel := os.environ.get('BROWSER_CHANNEL'):
            options['channel'] = channel
        browser = driver.chromium.launch(**options)
        yield browser
        browser.close()


@pytest.fixture
def page(browser, ui_server):
    context = browser.new_context(viewport={'width': 1440, 'height': 1100})
    page = context.new_page()
    page.add_init_script("localStorage.setItem('RespiraScope-language','zh')")
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    yield page
    page.unroute_all(behavior='ignoreErrors')
    context.close()
    assert not errors
