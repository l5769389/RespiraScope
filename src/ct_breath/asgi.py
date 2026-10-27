import os

from ct_breath.app import create_socket_app
from ct_breath.core.config import get_config, with_runtime_ports


def backend_port_from_argv(argv: list[str] | None = None) -> int | None:
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    for index, arg in enumerate(args):
        if arg == "--port" and index + 1 < len(args):
            return int(args[index + 1])
        if arg.startswith("--port="):
            return int(arg.split("=", 1)[1])
    return None


def create_runtime_app():
    config = with_runtime_ports(
        get_config(),
        backend_port=int(os.environ["RESPIRASCOPE_BACKEND_PORT"]) if "RESPIRASCOPE_BACKEND_PORT" in os.environ else None,
        console_port=int(os.environ["RESPIRASCOPE_CONSOLE_PORT"]) if "RESPIRASCOPE_CONSOLE_PORT" in os.environ else None,
    )
    backend_port = backend_port_from_argv()
    if backend_port is not None:
        config = with_runtime_ports(config, backend_port=backend_port)
    return create_socket_app(config)


app = create_runtime_app()
