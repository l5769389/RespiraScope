import uvicorn
from pathlib import Path

from ct_breath.app import create_socket_app
from ct_breath.config import get_config, with_runtime_ports
from ct_breath.frontend_static import endpoint_text, endpoint_url, start_static_frontend, stop_static_frontends
from ct_breath.ports import find_available_port, is_port_available


def print_status(message: str = ""):
    if message:
        print(f"[RespiraScope] {message}", flush=True)
    else:
        print(flush=True)


def print_warning(message: str):
    print_status(f"WARNING: {message}")


def print_start_banner():
    print_status()
    print_status(f"Starting from {Path.cwd()}")
    print_status("Press Ctrl+C to stop the server.")
    print_status()


def choose_runtime_port(name: str, host: str, preferred_port: int, warnings: list[str]) -> int:
    selected_port = find_available_port(host, preferred_port)
    if selected_port != preferred_port:
        warnings.append(f"{name} port {preferred_port} is not available; using {selected_port}.")
    return selected_port


def print_startup_summary(config, console_url: str | None, warnings: list[str]):
    print_status(f"Config: {config.config_path}")
    print_status(endpoint_text("Backend API", config.backend_host, config.backend_port))
    if console_url:
        print_status(f"Open Console: {console_url}")
    elif config.console_enabled:
        print_warning("Breath Console is enabled but could not be started.")
    else:
        print_status("Breath Console: disabled")

    if config.enable_mock_signal:
        mock_endpoint = f"{config.mock_signal_bind_host}:{config.sensor_port}"
        print_status(f"Mock signal: enabled (browser sessions are isolated; legacy TCP endpoint {mock_endpoint})")
    else:
        print_status(f"Sensor input: {config.sensor_host}:{config.sensor_port}")
    print_status(f"Record storage: {config.record_storage_root}")

    for warning in warnings:
        print_warning(warning)
    print_status()


def try_start_frontend(directory: str, host: str, port: int, name: str, config):
    try:
        return start_static_frontend(directory, host, port, name, config)
    except OSError as exc:
        print_warning(f"{endpoint_text(name, host, port)} failed to start: {exc}")
    except FileNotFoundError as exc:
        print_warning(f"{name} failed to start: {exc}")
    return None


def main():
    config = get_config()
    print_start_banner()
    warnings = []
    backend_port = choose_runtime_port("Backend API", config.backend_host, config.backend_port, warnings)
    if backend_port != config.backend_port:
        config = with_runtime_ports(config, backend_port=backend_port)
    if config.console_enabled:
        console_port = choose_runtime_port("Breath Console", config.console_host, config.console_port, warnings)
        if console_port != config.console_port:
            config = with_runtime_ports(config, console_port=console_port)
    if config.enable_mock_signal and not is_port_available(config.mock_signal_bind_host, config.sensor_port):
        warnings.append(
            f"Mock TCP endpoint {config.mock_signal_bind_host}:{config.sensor_port} is already in use. "
            "Cloud/browser mock sessions still work; free the port or change [sensor].port only for legacy TCP clients."
        )

    frontends = []
    console_url = None
    try:
        if config.console_enabled:
            frontend = try_start_frontend(
                "frontend-console",
                config.console_host,
                config.console_port,
                "Breath Console",
                config,
            )
            if frontend:
                frontends.append(frontend)
                console_url = endpoint_url(config.console_host, config.console_port)
        else:
            warnings.append("Breath Console is disabled in [console].enabled.")

        print_startup_summary(config, console_url, warnings)

        uvicorn.run(
            create_socket_app(config),
            host=config.backend_host,
            port=config.backend_port,
            reload=False,
            log_level="warning",
            access_log=False,
        )
    finally:
        stop_static_frontends(frontends)


if __name__ == "__main__":
    main()
