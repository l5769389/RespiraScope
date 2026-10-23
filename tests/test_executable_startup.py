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

from ct_breath import ports
from ct_breath.config import AppConfig
from ct_breath.frontend_static import start_static_frontend, stop_static_frontends
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
            frontend = start_static_frontend('frontend-console', '127.0.0.1',
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
    import ct_breath.config as config
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
        source = Path(__file__).resolve().parents[1] / 'src'
        used_ports = {preferred, sensor.getsockname()[1]}
        for index in range(2):
            log_path = tmp_path / f'start-{index}.log'
            log = stack.enter_context(log_path.open('w', encoding='utf-8'))
            process = subprocess.Popen(
                [sys.executable, '-m', 'ct_breath', '--config', str(config_path)],
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
            for url in [api_url + '/openapi.json', ui_url + '/', ui_url + '/monitor/vendor/echarts.min.js']:
                with urlopen(url, timeout=5) as response:
                    assert response.status == 200
            with urlopen(ui_url + '/runtime-config.js', timeout=5) as response:
                payload = json.loads(response.read().decode().split(' = ', 1)[1].rstrip(';\n'))
            assert payload['backendPort'] == int(api_port)
            assert payload['consolePort'] == int(ui_port)
            assert 'already in use' in output
