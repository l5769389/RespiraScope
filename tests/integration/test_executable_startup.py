import json
import os
import re
import runpy
import socket
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from urllib.request import urlopen

import pytest

from ct_breath.runtime import ports
from ct_breath.core.config import AppConfig
from ct_breath.runtime.static_server import start_static_frontend, stop_static_frontends
from ct_breath.main import main


@pytest.mark.parametrize('occupied_host, new_host', [
    ('127.0.0.1', '127.0.0.1'), ('127.0.0.1', '0.0.0.0'), ('0.0.0.0', '127.0.0.1'),
])
def test_reserved_port_skips_occupied_and_remains_owned(occupied_host, new_host):
    with socket.create_server((occupied_host, 0)) as occupied:
        preferred = occupied.getsockname()[1]
        with ports.reserve_listener(new_host, preferred) as reserved:
            selected = reserved.getsockname()[1]
            assert selected != preferred
            assert not ports.is_port_available('127.0.0.1', selected)
        assert ports.is_port_available('127.0.0.1', selected)


def test_reserved_port_can_fall_back_to_os_assignment():
    with socket.create_server(('127.0.0.1', 0)) as occupied:
        preferred = occupied.getsockname()[1]
        with ports.reserve_listener('127.0.0.1', preferred, max_attempts=0,
                                    excluded_ports={preferred}) as reserved:
            assert reserved.getsockname()[1] != preferred


def test_frontend_uses_reserved_socket_and_actual_backend_port(tmp_path):
    with ports.reserve_listener('127.0.0.1', 0) as backend:
        backend_port = backend.getsockname()[1]
        with ports.reserve_listener('127.0.0.1', backend_port) as ui:
            ui_port = ui.getsockname()[1]
            config = AppConfig(backend_port=backend_port, console_port=ui_port,
                               record_storage_root=tmp_path)
            frontend = start_static_frontend('console', '127.0.0.1',
                                             ui_port, 'test-ui', config, sock=ui)
            try:
                with urlopen(f'http://127.0.0.1:{ui_port}/runtime-config.js') as response:
                    payload = response.read().decode().split(' = ', 1)[1].rstrip(';\n')
                assert json.loads(payload)['backendPort'] == backend_port
                assert json.loads(payload)['consolePort'] == ui_port
                with urlopen(f'http://127.0.0.1:{ui_port}/') as response:
                    assert response.status == 200
            finally:
                stop_static_frontends([frontend])


def test_windows_defaults_do_not_require_a_d_drive(monkeypatch, tmp_path):
    import ct_breath.core.config as config
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    values = runpy.run_path(config.__file__)
    assert values['DEFAULT_CONFIG_PATH'] == tmp_path / 'RespiraScope/config/breath.toml'
    assert values['DEFAULT_RECORD_STORAGE_ROOT'] == tmp_path / 'RespiraScope/records'
    values['ensure_config_file'](values['DEFAULT_CONFIG_PATH'])
    assert values['DEFAULT_CONFIG_PATH'].is_file()


def test_frozen_executable_rejects_development_reload(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    assert main(['--reload']) == 2
    assert '--reload' in capsys.readouterr().err


def test_two_instances_with_occupied_ports_print_working_urls(tmp_path):
    """Exercise the real entry point, API, bundled assets and runtime port wiring."""
    def stop(process):
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    with ExitStack() as stack:
        occupied = stack.enter_context(socket.create_server(('127.0.0.1', 0)))
        sensor = stack.enter_context(socket.create_server(('127.0.0.1', 0)))
        preferred = occupied.getsockname()[1]
        config_path = tmp_path / 'breath.toml'
        config_path.write_text(
            f'[backend]\nhost="127.0.0.1"\nport={preferred}\n'
            f'[console]\nhost="127.0.0.1"\nport={preferred}\n'
            f'[sensor]\nport={sensor.getsockname()[1]}\n'
            f'[record]\nstorage_root={json.dumps(str(tmp_path / "records"))}\n',
            encoding='utf-8',
        )
        source = Path(__file__).resolve().parents[2] / 'src'
        used_ports = {preferred, sensor.getsockname()[1]}
        for index in range(2):
            log_path = tmp_path / f'start-{index}.log'
            log = stack.enter_context(log_path.open('w', encoding='utf-8'))
            process = subprocess.Popen(
                [sys.executable, '-m', 'ct_breath', '--no-browser', '--config', str(config_path)],
                cwd=tmp_path, env={**os.environ, 'PYTHONPATH': str(source), 'PYTHONUTF8': '1'},
                stdout=log, stderr=subprocess.STDOUT,
            )
            stack.callback(stop, process)
            deadline = time.monotonic() + 30
            while True:
                output = log_path.read_text(encoding='utf-8')
                api_match = re.search(r'Backend API: (http://127.0.0.1:(\d+))', output)
                ui_match = re.search(r'Open Console: (http://127.0.0.1:(\d+))', output)
                if api_match and ui_match:
                    break
                assert process.poll() is None, output
                assert time.monotonic() < deadline, output
                time.sleep(0.05)
            api_url, api_port = api_match.groups()
            ui_url, ui_port = ui_match.groups()
            assert int(api_port) not in used_ports
            used_ports.add(int(api_port))
            assert int(ui_port) not in used_ports
            used_ports.add(int(ui_port))
            for url in [api_url + '/openapi.json', ui_url + '/', ui_url + '/vendor/echarts.min.js']:
                with urlopen(url, timeout=5) as response:
                    assert response.status == 200
            with urlopen(ui_url + '/runtime-config.js', timeout=5) as response:
                payload = json.loads(response.read().decode().split(' = ', 1)[1].rstrip(';\n'))
            assert payload['backendPort'] == int(api_port)
            assert payload['consolePort'] == int(ui_port)
            assert 'already in use' in output


@pytest.mark.parametrize('reload', [False, True])
def test_startup_opens_actual_console_once_after_services_are_ready(tmp_path, reload):
    """Use real servers, replacing only the external browser with a URL recorder."""
    source = Path(__file__).resolve().parents[2] / 'src'
    config_path = tmp_path / 'breath.toml'
    config_path.write_text(
        '[backend]\nhost="127.0.0.1"\nport=0\n'
        '[console]\nhost="127.0.0.1"\nport=0\n'
        '[mock]\nenabled=false\n'
        f'[record]\nstorage_root={json.dumps(str(tmp_path / "records"))}\n',
        encoding='utf-8',
    )
    probe = tmp_path / 'opened.jsonl'
    launcher = '''
import json, os, webbrowser
from urllib.request import urlopen
from ct_breath.main import main
class Probe(webbrowser.BaseBrowser):
    def open(self, url, new=0, autoraise=True):
        with urlopen(url + '/runtime-config.js', timeout=2) as response:
            config = json.loads(response.read().decode().split(' = ', 1)[1].rstrip(';\\n'))
        with urlopen(f"http://127.0.0.1:{config['backendPort']}/health", timeout=2) as response:
            status = response.status
        with open(os.environ['BROWSER_PROBE'], 'a') as output:
            output.write(json.dumps({'url':url, 'health':status}) + '\\n')
        return True
webbrowser.register('probe', None, Probe(), preferred=True)
raise SystemExit(main())
'''
    log_path = tmp_path / 'startup.log'
    with log_path.open('w') as log:
        process = subprocess.Popen(
            [sys.executable, '-c', launcher, '--config', str(config_path), *(['--reload'] if reload else [])],
            cwd=tmp_path,
            env={**os.environ, 'PYTHONPATH': str(source), 'BROWSER_PROBE': str(probe)},
            stdout=log, stderr=subprocess.STDOUT,
        )
    try:
        deadline = time.monotonic() + 30
        while not probe.exists() or not probe.read_text().strip():
            assert process.poll() is None, log_path.read_text()
            assert time.monotonic() < deadline, log_path.read_text()
            time.sleep(0.05)
        time.sleep(0.5)
        calls = [json.loads(line) for line in probe.read_text().splitlines()]
        console_url = re.search(r'Open Console: (http://\S+)', log_path.read_text())[1]
        assert calls == [{'url': console_url, 'health': 200}]
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
