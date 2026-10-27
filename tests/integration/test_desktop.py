import runpy
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_windows_build_is_a_windowed_application(monkeypatch):
    build = runpy.run_path('scripts/packaging/build_exe.py')
    monkeypatch.setattr(sys, 'platform', 'win32')
    command = build['build_command'](Path.cwd(), False, False)
    assert '--windowed' in command
    assert '--console' not in command


@pytest.mark.parametrize('gui_failure', [False, True])
def test_desktop_stops_backend_when_window_closes_or_fails(monkeypatch, gui_failure):
    from ct_breath.runtime.desktop import run_desktop
    stopped = threading.Event()
    class Server:
        started = False
        should_exit = False
        def run(self, sockets):
            assert sockets == ['reserved']
            self.started = True
            while not self.should_exit:
                stopped.wait(0.01)
            stopped.set()
    server = Server()
    opened = []
    def create_window(title, url, **kwargs):
        assert server.started
        opened.append(url)
        return SimpleNamespace(destroy=lambda: None)
    def start(**kwargs):
        if gui_failure:
            raise RuntimeError('renderer missing')
    monkeypatch.setitem(sys.modules, 'webview', SimpleNamespace(
        settings={}, create_window=create_window, start=start))
    if gui_failure:
        with pytest.raises(RuntimeError, match='renderer missing'):
            run_desktop(server, ['reserved'], 'http://127.0.0.1:5188/')
    else:
        run_desktop(server, ['reserved'], 'http://127.0.0.1:5188/')
    assert opened == ['http://127.0.0.1:5188/']
    assert stopped.is_set()


def test_failed_backend_never_opens_a_window(monkeypatch):
    from ct_breath.runtime.desktop import run_desktop
    class Server:
        started = False
        should_exit = False
        def run(self, sockets):
            raise RuntimeError('startup failed')
    opened = []
    monkeypatch.setitem(sys.modules, 'webview', SimpleNamespace(
        settings={}, create_window=lambda *a, **k: opened.append(a)))
    with pytest.raises(RuntimeError, match='startup failed'):
        run_desktop(Server(), [], 'http://127.0.0.1:5188/')
    assert not opened


def test_desktop_main_closes_real_services_without_opening_browser(monkeypatch, tmp_path):
    import json
    from urllib.request import urlopen
    import webbrowser
    from ct_breath.core.config import AppConfig
    from ct_breath.main import main
    from ct_breath.runtime.ports import is_port_available
    import ct_breath.core.config as config_module

    monkeypatch.setattr(config_module, 'get_config', lambda: AppConfig(
        backend_host='127.0.0.1', backend_port=0,
        console_host='127.0.0.1', console_port=0,
        sensor_port=0, record_storage_root=tmp_path))
    urls = []
    ports = []
    def create_window(title, url, **kwargs):
        urls.append(url)
        return SimpleNamespace(destroy=lambda: None)
    def start(**kwargs):
        with urlopen(urls[0] + '/runtime-config.js', timeout=2) as response:
            payload = json.loads(response.read().decode().split(' = ',1)[1].rstrip(';\n'))
        ports.extend([payload['backendPort'], payload['consolePort']])
        for url in [f'http://127.0.0.1:{ports[0]}/health', urls[0] + '/assets/logo.ico']:
            with urlopen(url, timeout=2) as response:
                assert response.status == 200
    monkeypatch.setitem(sys.modules, 'webview', SimpleNamespace(
        settings={}, create_window=create_window, start=start))
    def unexpected_browser(*a, **k):
        pytest.fail('Desktop must not open an external browser')
    monkeypatch.setattr(webbrowser, 'open', unexpected_browser)
    assert main([], desktop=True) == 0
    assert len(urls) == 1
    assert all(is_port_available('127.0.0.1', port) for port in ports)


def test_windowed_startup_errors_go_to_log_and_dialog(monkeypatch, tmp_path):
    import ctypes
    from ct_breath import main
    from ct_breath.runtime.desktop import desktop_main
    dialogs = []
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setattr(ctypes, 'windll', SimpleNamespace(user32=SimpleNamespace(
        MessageBoxW=lambda *args: dialogs.append(args))), raising=False)
    def fail(*args, **kwargs):
        print('startup trace')
        raise RuntimeError('test startup failure')
    monkeypatch.setattr(main, 'main', fail)
    previous = sys.stdout, sys.stderr
    assert desktop_main([]) == 1
    assert (sys.stdout, sys.stderr) == previous
    log, = (tmp_path / 'RespiraScope/logs').glob('*.log')
    assert 'test startup failure' in log.read_text()
    assert 'startup trace' in log.read_text()
    assert str(log) in dialogs[0][1]
