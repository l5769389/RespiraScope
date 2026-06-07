import uvicorn

from ct_breath.app import create_socket_app
from ct_breath.config import get_config, with_runtime_ports
from ct_breath.frontend_static import endpoint_text, endpoint_url, start_static_frontend, stop_static_frontends
from ct_breath.ports import find_available_port


def try_start_frontend(directory: str, host: str, port: int, name: str, config):
    try:
        return start_static_frontend(directory, host, port, name, config)
    except OSError as exc:
        print(f"[RespiraScope] {endpoint_text(name, host, port)} failed to start: {exc}", flush=True)
    except FileNotFoundError as exc:
        print(f"[RespiraScope] {name} failed to start: {exc}", flush=True)
    return None


def main():
    config = get_config()
    backend_port = find_available_port(config.backend_host, config.backend_port)
    if backend_port != config.backend_port:
        print(
            f"[RespiraScope] backend port {config.backend_port} is in use; using {backend_port}",
            flush=True,
        )
        config = with_runtime_ports(config, backend_port=backend_port)
    frontends = []
    print(f"[RespiraScope] config: {config.config_path}", flush=True)
    print(f"[RespiraScope] {endpoint_text('backend', config.backend_host, config.backend_port)}", flush=True)
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
                print(f"[RespiraScope] {endpoint_text('console', config.console_host, config.console_port)}", flush=True)
                routes = []
                if config.monitor_enabled:
                    routes.append(f"monitor={console_url}/#monitor")
                if config.lab_enabled:
                    routes.append(f"setup={console_url}/#lab")
                print(f"[RespiraScope] console pages: {', '.join(routes)}", flush=True)
        else:
            print("[RespiraScope] front console disabled; Breath Console is not started", flush=True)

        uvicorn.run(
            create_socket_app(config),
            host=config.backend_host,
            port=config.backend_port,
            reload=False,
            log_level="info",
        )
    finally:
        stop_static_frontends(frontends)


if __name__ == "__main__":
    main()
