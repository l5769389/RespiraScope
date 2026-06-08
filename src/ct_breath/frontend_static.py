import json
import os
import posixpath
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from ct_breath.config import AppConfig, get_config
from ct_breath.session_ids import SESSION_HEADER, SESSION_QUERY_PARAM


def display_host(host: str) -> str:
    if host in {"0.0.0.0", "::", ""}:
        return "127.0.0.1"
    return host


def endpoint_url(host: str, port: int) -> str:
    return f"http://{display_host(host)}:{port}"


def endpoint_text(name: str, host: str, port: int) -> str:
    url = endpoint_url(host, port)
    if display_host(host) != host:
        return f"{name}: {url} (bind {host}:{port})"
    return f"{name}: {url}"


def runtime_config_payload(app_config: AppConfig) -> dict:
    backend_host = display_host(app_config.backend_host)
    return {
        "backendHost": backend_host,
        "backendPort": app_config.backend_port,
        "configPath": str(app_config.config_path),
        "mockSignalEnabled": app_config.enable_mock_signal,
        "sensorHost": display_host(app_config.sensor_host),
        "sensorPort": app_config.sensor_port,
        "consoleEnabled": app_config.console_enabled,
        "consoleHost": display_host(app_config.console_host),
        "consolePort": app_config.console_port if app_config.console_enabled else None,
        "apiDocsEnabled": app_config.console_enabled,
        "apiDocsHost": display_host(app_config.console_host),
        "apiDocsPort": app_config.console_port if app_config.console_enabled else None,
        "publicBasePath": app_config.public_base_path,
        "apiBasePath": app_config.public_api_base_path,
        "socketPath": app_config.public_socket_path,
        "monitorEnabled": app_config.monitor_enabled,
        "monitorHost": display_host(app_config.console_host),
        "monitorPort": app_config.console_port if app_config.console_enabled and app_config.monitor_enabled else None,
        "labEnabled": app_config.lab_enabled,
        "labHost": display_host(app_config.console_host),
        "labPort": app_config.console_port if app_config.console_enabled and app_config.lab_enabled else None,
        "record": {
            "prePoints": app_config.record_pre_points,
            "postPoints": app_config.record_post_points,
            "storageRoot": str(app_config.record_storage_root),
        },
        "session": {
            "header": SESSION_HEADER,
            "queryParam": SESSION_QUERY_PARAM,
            "idleTimeoutSeconds": app_config.session_idle_timeout_seconds,
        },
    }


class ConfigStaticHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, app_config=None, frontend_roots=None, **kwargs):
        self.app_config = app_config or get_config()
        self.frontend_roots = frontend_roots or {}
        super().__init__(*args, directory=directory, **kwargs)

    def strip_public_base_path(self, path: str) -> str:
        base_path = self.app_config.public_base_path
        if base_path and (path == base_path or path.startswith(f"{base_path}/")):
            return path[len(base_path):] or "/"
        return path

    def translate_path(self, path):
        parsed_path = self.strip_public_base_path(urlparse(path).path)
        root = Path(self.directory)
        relative_path = parsed_path

        for prefix, frontend_root in self.frontend_roots.items():
            route = f"/{prefix}"
            if parsed_path == route or parsed_path.startswith(f"{route}/"):
                root = Path(frontend_root)
                relative_path = parsed_path[len(route):] or "/"
                break

        relative_path = posixpath.normpath(unquote(relative_path))
        words = [
            word
            for word in relative_path.split("/")
            if word and word not in {os.curdir, os.pardir}
        ]
        resolved = root
        for word in words:
            resolved = resolved / word
        return str(resolved)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.strip_public_base_path(urlparse(self.path).path) == "/runtime-config.js":
            self.serve_runtime_config()
            return
        super().do_GET()

    def serve_runtime_config(self):
        content = f"window.CT_BREATH_RUNTIME_CONFIG = {json.dumps(runtime_config_payload(self.app_config))};\n"
        encoded = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def frontend_directory(directory: str) -> Path:
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(getattr(sys, "_MEIPASS", "")) / directory)
        candidates.append(Path(sys.executable).resolve().parent / directory)
    candidates.extend([
        Path.cwd() / directory,
        project_root() / directory,
    ])

    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    return candidates[0].resolve()


def create_static_server(directory: str, host: str, port: int, app_config: AppConfig):
    root = frontend_directory(directory)
    if not root.is_dir():
        raise FileNotFoundError(f"Static directory does not exist: {root}")
    frontend_roots = {}
    if directory == "frontend-console":
        frontend_roots = {
            "lab": frontend_directory("frontend-lab"),
            "monitor": frontend_directory("frontend-monitor"),
            "guide": frontend_directory("frontend-guide"),
            "api-docs": frontend_directory("frontend-api-docs"),
        }
    handler = partial(
        ConfigStaticHandler,
        directory=str(root),
        app_config=app_config,
        frontend_roots=frontend_roots,
    )
    return ThreadingHTTPServer((host, port), handler), root


def serve_static_frontend(directory: str, host: str, port: int, name: str, app_config: AppConfig | None = None) -> int:
    config = app_config or get_config()
    server, root = create_static_server(directory, host, port, config)
    print(endpoint_text(name, host, port), flush=True)
    print(f"Serving: {root}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


def start_static_frontend(directory: str, host: str, port: int, name: str, app_config: AppConfig):
    server, root = create_static_server(directory, host, port, app_config)
    thread = threading.Thread(target=server.serve_forever, name=name, daemon=True)
    thread.start()
    return {
        "name": name,
        "server": server,
        "thread": thread,
        "root": root,
        "host": host,
        "port": port,
    }


def stop_static_frontends(frontends: list[dict]):
    for frontend in frontends:
        frontend["server"].shutdown()
        frontend["server"].server_close()
