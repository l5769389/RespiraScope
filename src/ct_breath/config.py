import os
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


WINDOWS_CONFIG_PATH = Path("D:/ct/breath-config/breath.toml")
LINUX_CONFIG_PATH = Path("/ct/breath-config/breath.toml")
WINDOWS_RECORD_STORAGE_ROOT = Path("D:/ct/breath-file")
LINUX_RECORD_STORAGE_ROOT = Path("/ct/breath-records")
CONFIG_DIRECTORIES = [
    Path("D:/ct/breath-config"),
    Path("/ct/breath-config"),
]
CONFIG_FILENAMES = [
    "breath.toml",
    "config.toml",
]
DEFAULT_CONFIG_PATH = WINDOWS_CONFIG_PATH if os.name == "nt" else LINUX_CONFIG_PATH
DEFAULT_RECORD_STORAGE_ROOT = WINDOWS_RECORD_STORAGE_ROOT if os.name == "nt" else LINUX_RECORD_STORAGE_ROOT
DEFAULT_CONFIG_TEXT = """[mock]
# Enable the built-in simulated breath signal server and /mock/* APIs.
enabled = true
bind_host = "0.0.0.0"

[sensor]
# Breath device TCP stream. When mock.enabled = true, this is also the local
# simulated signal port.
host = "localhost"
port = 8088

[backend]
host = "0.0.0.0"
port = 8000

[console]
# Single frontend web console. It contains Realtime Monitor and Mock Lab,
# so dev/prod only start one frontend server.
enabled = true
host = "127.0.0.1"
port = 5175

[lab]
enabled = true

[monitor]
enabled = true

[record]
# Extra samples kept before Record Start and after Record End.
pre_points = 100
post_points = 100
# Server-side root for temporary session record files.
storage_root = "{record_storage_root}"

[session]
# Anonymous browser sessions are isolated from each other and cleaned up after
# this idle period.
idle_timeout_seconds = 14400

[proxy]
# Public path prefixes used when RespiraScope is reverse-proxied under a
# subpath such as /breath. Leave empty for direct local access.
public_base_path = ""
api_base_path = ""
socket_path = ""
""".format(record_storage_root=str(DEFAULT_RECORD_STORAGE_ROOT).replace("\\", "/"))


@dataclass(frozen=True)
class AppConfig:
    enable_mock_signal: bool = True
    sensor_host: str = "localhost"
    sensor_port: int = 8088
    mock_signal_bind_host: str = "0.0.0.0"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    enable_front_console: bool = True
    console_host: str = "127.0.0.1"
    console_port: int = 5175
    enable_front_lab: bool = True
    lab_host: str = "127.0.0.1"
    lab_port: int = 5174
    enable_front_monitor: bool = True
    monitor_host: str = "127.0.0.1"
    monitor_port: int = 5175
    record_pre_points: int = 100
    record_post_points: int = 100
    record_storage_root: Path = DEFAULT_RECORD_STORAGE_ROOT
    session_idle_timeout_seconds: int = 14400
    public_base_path: str = ""
    public_api_base_path: str = ""
    public_socket_path: str = ""
    config_path: Path = DEFAULT_CONFIG_PATH

    @property
    def lab_enabled(self) -> bool:
        return self.enable_mock_signal and self.enable_front_lab

    @property
    def monitor_enabled(self) -> bool:
        return self.enable_front_monitor

    @property
    def console_enabled(self) -> bool:
        return self.enable_front_console


def with_runtime_ports(
    config: AppConfig,
    *,
    backend_port: int | None = None,
    console_port: int | None = None,
) -> AppConfig:
    updates = {}
    if backend_port is not None:
        updates["backend_port"] = backend_port
    if console_port is not None:
        updates["console_port"] = console_port
    if not updates:
        return config
    return replace(config, **updates)


def resolve_config_path(path: str | Path | None = None) -> Path:
    if path:
        return Path(path)

    for directory in CONFIG_DIRECTORIES:
        for filename in CONFIG_FILENAMES:
            candidate = directory / filename
            if candidate.exists():
                return candidate

    for directory in CONFIG_DIRECTORIES:
        if directory.exists():
            toml_files = sorted(directory.glob("*.toml"))
            if toml_files:
                return toml_files[0]

    return DEFAULT_CONFIG_PATH


def read_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as file:
        return tomllib.load(file)


def ensure_config_file(path: Path) -> Path:
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
    return path


def section(config_data: dict[str, Any], name: str) -> dict[str, Any]:
    value = config_data.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"Config section [{name}] must be a table")
    return value


def config_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def config_int(value: Any, default: int) -> int:
    if value is None:
        return default
    return int(value)


def config_str(value: Any, default: str) -> str:
    if value is None:
        return default
    return str(value)


def config_path_prefix(value: Any, default: str = "") -> str:
    text = config_str(value, default).strip()
    if not text or text == "/":
        return ""
    if not text.startswith("/"):
        text = f"/{text}"
    return text.rstrip("/")


def get_config(path: str | Path | None = None) -> AppConfig:
    config_path = resolve_config_path(path)
    ensure_config_file(config_path)
    config_data = read_config_file(config_path)
    mock = section(config_data, "mock")
    sensor = section(config_data, "sensor")
    backend = section(config_data, "backend")
    console = section(config_data, "console")
    lab = section(config_data, "lab")
    monitor = section(config_data, "monitor")
    record = section(config_data, "record")
    session_config = section(config_data, "session")
    proxy = section(config_data, "proxy")

    defaults = AppConfig(config_path=config_path)
    return AppConfig(
        enable_mock_signal=config_bool(mock.get("enabled"), defaults.enable_mock_signal),
        sensor_host=config_str(sensor.get("host"), defaults.sensor_host),
        sensor_port=config_int(sensor.get("port"), defaults.sensor_port),
        mock_signal_bind_host=config_str(mock.get("bind_host"), defaults.mock_signal_bind_host),
        backend_host=config_str(backend.get("host"), defaults.backend_host),
        backend_port=config_int(backend.get("port"), defaults.backend_port),
        enable_front_console=config_bool(console.get("enabled"), defaults.enable_front_console),
        console_host=config_str(console.get("host"), config_str(monitor.get("host"), defaults.console_host)),
        console_port=config_int(console.get("port"), config_int(monitor.get("port"), defaults.console_port)),
        enable_front_lab=config_bool(lab.get("enabled"), defaults.enable_front_lab),
        lab_host=config_str(lab.get("host"), defaults.lab_host),
        lab_port=config_int(lab.get("port"), defaults.lab_port),
        enable_front_monitor=config_bool(monitor.get("enabled"), defaults.enable_front_monitor),
        monitor_host=config_str(monitor.get("host"), defaults.monitor_host),
        monitor_port=config_int(monitor.get("port"), defaults.monitor_port),
        record_pre_points=max(0, config_int(record.get("pre_points"), defaults.record_pre_points)),
        record_post_points=max(0, config_int(record.get("post_points"), defaults.record_post_points)),
        record_storage_root=Path(config_str(record.get("storage_root"), str(defaults.record_storage_root))),
        session_idle_timeout_seconds=max(
            60,
            config_int(session_config.get("idle_timeout_seconds"), defaults.session_idle_timeout_seconds),
        ),
        public_base_path=config_path_prefix(proxy.get("public_base_path"), defaults.public_base_path),
        public_api_base_path=config_path_prefix(proxy.get("api_base_path"), defaults.public_api_base_path),
        public_socket_path=config_path_prefix(proxy.get("socket_path"), defaults.public_socket_path),
        config_path=config_path,
    )


settings = get_config()

# Backward-compatible alias for older local code.
open_mock_server = settings.enable_mock_signal
