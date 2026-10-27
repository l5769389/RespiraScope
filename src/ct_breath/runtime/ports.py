import errno
import socket
from contextlib import closing


def _socket_family(host: str) -> socket.AddressFamily:
    if ":" in host and host not in {"localhost", "127.0.0.1"}:
        return socket.AF_INET6
    return socket.AF_INET


def _has_listener(host: str, port: int) -> bool:
    # Wildcard addresses are bind targets; probe their loopback address.
    probe_host = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)
    try:
        with socket.create_connection((probe_host, port), timeout=0.2):
            return True
    except OSError:
        return False


def reserve_listener(
    host: str, preferred_port: int, *, max_attempts: int = 100,
    excluded_ports: set[int] | None = None,
) -> socket.socket:
    """Select and hold a listening socket until the caller closes it.

    Passing the same socket to the server avoids the probe/close/bind race.
    After nearby ports are exhausted, let the OS assign an available port.
    """
    bind_host = host or "0.0.0.0"
    excluded = excluded_ports or set()
    candidates = range(preferred_port, min(preferred_port + max_attempts + 1, 65536)) if preferred_port > 0 else ()
    for port in [*candidates, *([0] * 100)]:
        if port and port in excluded:
            continue
        # On Windows, binding a specific address can succeed beside an
        # existing non-exclusive wildcard listener. Do not shadow that service.
        if port and _has_listener(bind_host, port):
            continue
        listener = socket.socket(_socket_family(bind_host), socket.SOCK_STREAM)
        try:
            # Do not use SO_REUSEADDR: wildcard and loopback listeners can
            # otherwise overlap on macOS; Windows can steal existing binds.
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind((bind_host, port))
            listener.listen(socket.SOMAXCONN)
            if listener.getsockname()[1] in excluded:
                listener.close()
                continue
            return listener
        except OSError as exc:
            listener.close()
            if port and exc.errno in {errno.EADDRINUSE, errno.EACCES}:
                continue
            raise
        except BaseException:
            listener.close()
            raise
    raise OSError("Could not reserve an available listening port")


def is_port_available(host: str, port: int) -> bool:
    if port <= 0:
        return False
    bind_host = host or "0.0.0.0"
    # Some systems allow SO_REUSEADDR listeners on both wildcard and loopback
    # addresses. A successful bind alone can then hide an existing service.
    if _has_listener(bind_host, port):
        return False
    try:
        with closing(socket.create_server((bind_host, port), family=_socket_family(bind_host))):
            return True
    except OSError:
        return False


def find_available_port(
    host: str, preferred_port: int, *, max_attempts: int = 100,
    excluded_ports: set[int] | None = None,
) -> int:
    bind_host = host or "0.0.0.0"
    excluded = excluded_ports or set()
    if preferred_port > 0:
        for port in range(preferred_port, min(preferred_port + max_attempts + 1, 65536)):
            if port not in excluded and is_port_available(bind_host, port):
                return port

    while True:
        with closing(socket.create_server((bind_host, 0), family=_socket_family(bind_host))) as server:
            port = int(server.getsockname()[1])
            if port not in excluded:
                return port
