import socket
from contextlib import closing


def _socket_family(host: str) -> socket.AddressFamily:
    if ":" in host and host not in {"localhost", "127.0.0.1"}:
        return socket.AF_INET6
    return socket.AF_INET


def is_port_available(host: str, port: int) -> bool:
    if port <= 0:
        return False
    bind_host = host or "0.0.0.0"
    try:
        with closing(socket.create_server((bind_host, port), family=_socket_family(bind_host))):
            return True
    except OSError:
        return False


def find_available_port(host: str, preferred_port: int, *, max_attempts: int = 100) -> int:
    bind_host = host or "0.0.0.0"
    if preferred_port > 0:
        for port in range(preferred_port, preferred_port + max_attempts + 1):
            if is_port_available(bind_host, port):
                return port

    with closing(socket.create_server((bind_host, 0), family=_socket_family(bind_host))) as server:
        return int(server.getsockname()[1])
