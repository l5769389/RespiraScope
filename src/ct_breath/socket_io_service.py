import socketio
from collections.abc import Callable

from ct_breath.logger import logger


namespace = "/breath"
client_ids: set[str] = set()
snapshot_provider: Callable[[], list[dict]] | None = None

sio = socketio.AsyncServer(
    cors_allowed_origins="*",
    transports=["websocket"],
    namespace=namespace,
    ping_timeout=120,
    ping_interval=25,
    async_mode="asgi",
)


@sio.event(namespace=namespace)
async def connect(sid, environ):
    client_ids.add(sid)
    logger.info(f"Socket.IO client connected: {sid}")
    logger.info(f"Socket.IO connected clients: {len(client_ids)}")
    await send_recent_snapshot(sid)


@sio.event(namespace=namespace)
async def disconnect(sid):
    client_ids.discard(sid)
    logger.info(f"Socket.IO client disconnected: {sid}")
    logger.info(f"Socket.IO connected clients: {len(client_ids)}")


@sio.event(namespace=namespace)
async def message(sid, data):
    pass


async def send_socket_io_message(msg):
    if not client_ids:
        return
    try:
        await sio.emit("breath", msg, namespace=namespace)
    except Exception as e:
        logger.error(f"send socket_io msg error:{e}")


def set_snapshot_provider(provider: Callable[[], list[dict]] | None):
    global snapshot_provider
    snapshot_provider = provider


async def send_recent_snapshot(sid):
    if snapshot_provider is None:
        return
    try:
        for message in snapshot_provider():
            await sio.emit("breath", message, namespace=namespace, room=sid)
    except Exception as e:
        logger.error(f"send socket_io snapshot error:{e}")
