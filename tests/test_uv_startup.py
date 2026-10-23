from pathlib import Path

import pytest

from ct_breath import frontend_static
from ct_breath.config import resolve_config_path
from ct_breath.main import main


def test_ui_port_fallback_skips_the_backend_port(monkeypatch):
    from ct_breath import ports
    from ct_breath.main import choose_runtime_port

    monkeypatch.setattr(ports, 'is_port_available', lambda host, port: port in {8001, 8002})
    warnings = []
    assert choose_runtime_port('Web UI', '127.0.0.1', 8000, warnings, excluded_ports={8001}) == 8002
    assert warnings


def test_help_exits_without_starting_services(capsys):
    with pytest.raises(SystemExit) as result:
        main(['--help'])
    assert result.value.code == 0
    output = capsys.readouterr().out
    assert '--reload' in output
    assert '--config' in output


def test_explicit_environment_config_reaches_child_processes(monkeypatch, tmp_path):
    config = tmp_path / 'breath.toml'
    config.write_text('[mock]\nenabled = false\n')
    monkeypatch.setenv('RESPIRASCOPE_CONFIG', str(config))
    assert resolve_config_path() == config
    override = tmp_path / 'override.toml'
    assert resolve_config_path(override) == override


def test_frontend_resources_are_part_of_the_python_package(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    root = Path(frontend_static.__file__).parent
    for name in ['console', 'monitor', 'lab', 'guide', 'api-docs']:
        directory = frontend_static.frontend_directory(f'frontend-{name}')
        assert directory.is_relative_to(root)
        assert (directory / 'index.html').is_file()


def test_wildcard_port_does_not_shadow_a_loopback_listener():
    import socket
    from ct_breath.ports import is_port_available
    with socket.create_server(('127.0.0.1',0)) as listener:
        port=listener.getsockname()[1]
        assert not is_port_available('0.0.0.0',port)
        assert not is_port_available('127.0.0.1',port)
    assert is_port_available('127.0.0.1',port)
