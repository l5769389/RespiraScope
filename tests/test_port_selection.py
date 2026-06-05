import socket
from contextlib import closing

from ct_breath.config import AppConfig, with_runtime_ports
from ct_breath.frontend_static import runtime_config_payload
from ct_breath.ports import find_available_port, is_port_available


def test_find_available_port_skips_occupied_port():
    host = "127.0.0.1"
    with closing(socket.create_server((host, 0))) as server:
        occupied_port = int(server.getsockname()[1])

        selected_port = find_available_port(host, occupied_port, max_attempts=10)

        assert selected_port != occupied_port
        assert selected_port > 0
        assert is_port_available(host, selected_port)


def test_with_runtime_ports_updates_backend_port_without_mutating_original():
    config = AppConfig(backend_port=8000, console_port=5175)

    updated = with_runtime_ports(config, backend_port=8001)

    assert config.backend_port == 8000
    assert updated.backend_port == 8001
    assert updated.console_port == 5175


def test_frontend_runtime_config_uses_selected_backend_port():
    config = with_runtime_ports(AppConfig(backend_port=8000), backend_port=8002)

    payload = runtime_config_payload(config)

    assert payload["backendPort"] == 8002


def test_frontend_runtime_config_includes_public_proxy_paths():
    config = AppConfig(
        public_base_path="/breath",
        public_api_base_path="/breath-api",
        public_socket_path="/breath-socket/socket.io",
    )

    payload = runtime_config_payload(config)

    assert payload["publicBasePath"] == "/breath"
    assert payload["apiBasePath"] == "/breath-api"
    assert payload["socketPath"] == "/breath-socket/socket.io"
