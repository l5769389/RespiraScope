import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from ct_breath.config import get_config, with_runtime_ports
from ct_breath.frontend_static import endpoint_text, endpoint_url, serve_static_frontend
from ct_breath.ports import find_available_port


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def start_process(name: str, command: list[str], cwd: Path) -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    print(f"[dev] starting {name}: {' '.join(command)}", flush=True)
    return subprocess.Popen(command, cwd=str(cwd), env=env)


def serve_static(directory: str, host: str, port: int, name: str, backend_port: int | None = None) -> int:
    config = get_config()
    if backend_port is not None:
        config = with_runtime_ports(config, backend_port=backend_port)
    return serve_static_frontend(directory, host, port, name, config)


def terminate_processes(processes: list[tuple[str, subprocess.Popen]]):
    for name, process in processes:
        if process.poll() is None:
            print(f"[dev] stopping {name}", flush=True)
            process.terminate()

    deadline = time.time() + 8
    for name, process in processes:
        while process.poll() is None and time.time() < deadline:
            time.sleep(0.1)
        if process.poll() is None:
            print(f"[dev] killing {name}", flush=True)
            process.kill()


def frontend_server_command(
    python: str,
    port: int,
    host: str,
    directory: str,
    name: str,
    backend_port: int,
) -> list[str]:
    return [
        python,
        "scripts/dev.py",
        "serve-static",
        directory,
        "--port",
        str(port),
        "--host",
        host,
        "--name",
        name,
        "--backend-port",
        str(backend_port),
    ]


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "serve-static":
        parser = argparse.ArgumentParser(description="Serve a RespiraScope static frontend.")
        parser.add_argument("command")
        parser.add_argument("directory")
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, required=True)
        parser.add_argument("--name", default="RespiraScope frontend")
        parser.add_argument("--backend-port", type=int)
        args = parser.parse_args()
        return serve_static(args.directory, args.host, args.port, args.name, args.backend_port)

    root = project_root()
    python = sys.executable
    config = get_config()
    backend_port = find_available_port(config.backend_host, config.backend_port)
    if backend_port != config.backend_port:
        print(f"[dev] backend port {config.backend_port} is in use; using {backend_port}", flush=True)
        config = with_runtime_ports(config, backend_port=backend_port)
    print(f"[dev] config: {config.config_path}", flush=True)

    processes: list[tuple[str, subprocess.Popen]] = []
    processes.append(
        (
            "backend",
            start_process(
                "backend",
                [
                    python,
                    "-m",
                    "uvicorn",
                    "ct_breath.asgi:app",
                    "--host",
                    config.backend_host,
                    "--port",
                    str(config.backend_port),
                    "--reload",
                    "--reload-dir",
                    "src",
                ],
                root,
            ),
        )
    )

    if config.console_enabled:
        processes.append(
            (
                "console",
                start_process(
                    "console",
                    frontend_server_command(
                        python,
                        config.console_port,
                        config.console_host,
                        "frontend-console",
                        "Breath Console",
                        config.backend_port,
                    ),
                    root,
                ),
            )
        )
    else:
        print("[dev] front console disabled; Breath Console is not started", flush=True)

    def handle_stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, handle_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_stop)

    print(f"[dev] {endpoint_text('backend', config.backend_host, config.backend_port)}", flush=True)
    if config.console_enabled:
        console_url = endpoint_url(config.console_host, config.console_port)
        print(f"[dev] {endpoint_text('console', config.console_host, config.console_port)}", flush=True)
        routes = []
        if config.monitor_enabled:
            routes.append(f"monitor={console_url}/#monitor")
        if config.lab_enabled:
            routes.append(f"setup={console_url}/#lab")
        print(f"[dev] console pages: {', '.join(routes)}", flush=True)

    try:
        while True:
            for name, process in processes:
                return_code = process.poll()
                if return_code is not None:
                    print(f"[dev] {name} exited with code {return_code}", flush=True)
                    return return_code
            time.sleep(0.4)
    except KeyboardInterrupt:
        return 0
    finally:
        terminate_processes(processes)


if __name__ == "__main__":
    raise SystemExit(main())
