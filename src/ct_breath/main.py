import argparse
import os
import signal
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path


def port_number(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Start RespiraScope API and web UI together with uv.")
    parser.add_argument("--config", type=Path, help="External TOML configuration file")
    parser.add_argument("--port", type=port_number, help="Preferred backend port")
    parser.add_argument("--ui-port", type=port_number, help="Preferred web UI port")
    parser.add_argument("--reload", action="store_true", help="Reload Python code during development; refresh the browser for UI edits")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open the web console")
    return parser.parse_args(argv)


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


def choose_runtime_port(
    name: str, host: str, preferred_port: int, warnings: list[str], *,
    excluded_ports: set[int] | None = None,
) -> int:
    from ct_breath.ports import find_available_port

    selected_port = find_available_port(host, preferred_port, excluded_ports=excluded_ports)
    if selected_port != preferred_port:
        warnings.append(f"{name} port {preferred_port} is not available; using {selected_port}.")
    return selected_port


def print_startup_summary(config, console_url: str | None, warnings: list[str]):
    from ct_breath.frontend_static import endpoint_text

    print_status(f"Config: {config.config_path}")
    print_status(endpoint_text("Backend API", config.backend_host, config.backend_port))
    if console_url:
        print_status(f"Open Console: {console_url}")
        if config.monitor_enabled:
            print_status(f"Monitor: {console_url}/#monitor")
        if config.lab_enabled:
            print_status(f"Mock Lab: {console_url}/#lab")
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


def try_start_frontend(directory: str, host: str, port: int, name: str, config, *, sock=None):
    from ct_breath.frontend_static import endpoint_text, start_static_frontend

    try:
        return start_static_frontend(directory, host, port, name, config, sock=sock)
    except OSError as exc:
        print_warning(f"{endpoint_text(name, host, port)} failed to start: {exc}")
    return None


def run_reloading_backend(config):
    env = os.environ.copy()
    env["RESPIRASCOPE_BACKEND_PORT"] = str(config.backend_port)
    env["RESPIRASCOPE_CONSOLE_PORT"] = str(config.console_port)
    process = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "ct_breath.asgi:app",
        "--host", config.backend_host, "--port", str(config.backend_port),
        "--reload", "--reload-dir", str(Path(__file__).parent),
        "--log-level", "warning", "--no-access-log",
    ], env=env)
    previous = signal.getsignal(signal.SIGTERM)

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        return process.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        signal.signal(signal.SIGTERM, previous)
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main(argv=None):
    args = parse_args(argv)
    if args.reload and getattr(sys, "frozen", False):
        print("--reload is only supported when running from Python source, not the packaged executable.", file=sys.stderr)
        return 2
    if args.config:
        os.environ["RESPIRASCOPE_CONFIG"] = str(args.config.expanduser().resolve())
    # Resolve the selected configuration before importing modules with runtime singletons.
    import uvicorn
    from ct_breath.config import get_config, with_runtime_ports
    from ct_breath.frontend_static import endpoint_url, stop_static_frontends
    from ct_breath.ports import is_port_available, reserve_listener

    config = with_runtime_ports(get_config(), backend_port=args.port, console_port=args.ui_port)
    print_start_banner()
    warnings = []
    frontends = []
    console_url = None
    with ExitStack() as listeners:
        # Hold both ports for the lifetime of the servers. Reload uses a child
        # process and retains uvicorn's own development-only port binding.
        backend_socket = None
        excluded = {config.sensor_port} if config.enable_mock_signal else set()
        if args.reload:
            backend_port = choose_runtime_port(
                "Backend API", config.backend_host, config.backend_port, warnings,
                excluded_ports=excluded,
            )
        else:
            backend_socket = listeners.enter_context(reserve_listener(
                config.backend_host, config.backend_port, excluded_ports=excluded,
            ))
            backend_port = backend_socket.getsockname()[1]
            if backend_port != config.backend_port:
                warnings.append(f"Backend API port {config.backend_port} is not available; using {backend_port}.")
        config = with_runtime_ports(config, backend_port=backend_port)
        console_socket = None
        if config.console_enabled:
            console_socket = listeners.enter_context(reserve_listener(
                config.console_host, config.console_port,
                excluded_ports=excluded | {backend_port},
            ))
            console_port = console_socket.getsockname()[1]
            if console_port != config.console_port:
                warnings.append(f"Breath Console port {config.console_port} is not available; using {console_port}.")
            config = with_runtime_ports(config, console_port=console_port)
        if config.enable_mock_signal and not is_port_available(config.mock_signal_bind_host, config.sensor_port):
            warnings.append(
                f"Mock TCP endpoint {config.mock_signal_bind_host}:{config.sensor_port} is already in use. "
                "Browser mock sessions still work; free the port or change [sensor].port only for legacy TCP clients."
            )

        try:
            if config.console_enabled:
                frontend = try_start_frontend(
                    "frontend-console", config.console_host, config.console_port,
                    "Breath Console", config, sock=console_socket,
                )
                if frontend:
                    frontends.append(frontend)
                    console_url = endpoint_url(config.console_host, config.console_port) + config.public_base_path
                else:
                    raise SystemExit("Web UI failed to start; check the address and packaged frontend resources.")
            else:
                warnings.append("Breath Console is disabled in [console].enabled.")

            if console_url and not args.no_browser:
                from ct_breath.browser_launch import start_browser_when_ready

                # The launcher owns this worker so --reload never opens another tab.
                listeners.callback(start_browser_when_ready(
                    console_url, endpoint_url(config.backend_host, config.backend_port) + "/health",
                ))

            if args.reload:
                print_startup_summary(config, console_url, warnings)
                return run_reloading_backend(config)
            from ct_breath.app import create_socket_app

            class ReadyServer(uvicorn.Server):
                async def startup(self, sockets=None):
                    await super().startup(sockets=sockets)
                    if self.started:
                        print_startup_summary(config, console_url, warnings)

            server = ReadyServer(uvicorn.Config(
                create_socket_app(config), host=config.backend_host, port=config.backend_port,
                log_level="warning", access_log=False,
            ))
            server.run(sockets=[backend_socket])
            return 0 if server.started else 1
        finally:
            stop_static_frontends(frontends)


if __name__ == "__main__":
    raise SystemExit(main())
