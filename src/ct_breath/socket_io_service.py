from collections.abc import Callable
from urllib.parse import parse_qs

import socketio

from ct_breath.logger import logger
from ct_breath.session_ids import SESSION_QUERY_PARAM, normalize_session_id, session_room


namespace = "/breath"
client_ids: set[str] = set()
client_sessions: dict[str, str | None] = {}
snapshot_provider: Callable[[], list[dict]] | None = None
snapshot_providers: dict[str, Callable[[], list[dict]]] = {}
session_touch_callback: Callable[[str], None] | None = None

sio = socketio.AsyncServer(
    cors_allowed_origins="*",
    transports=["websocket"],
    namespace=namespace,
    ping_timeout=120,
    ping_interval=25,
    async_mode="asgi",
)


@sio.event(namespace=namespace)
async def connect(sid, environ, auth=None):
    client_ids.add(sid)
    session_id = session_id_from_connect(environ, auth)
    client_sessions[sid] = session_id
    if session_id:
        await sio.enter_room(sid, session_room(session_id), namespace=namespace)
        touch_session(session_id)
    logger.info(f"Socket.IO client connected: {sid} session={session_id or '-'}")
    logger.info(f"Socket.IO connected clients: {len(client_ids)}")
    await send_recent_snapshot(sid, session_id)


@sio.event(namespace=namespace)
async def disconnect(sid):
    client_ids.discard(sid)
    session_id = client_sessions.pop(sid, None)
    if session_id:
        touch_session(session_id)
    logger.info(f"Socket.IO client disconnected: {sid} session={session_id or '-'}")
    logger.info(f"Socket.IO connected clients: {len(client_ids)}")


@sio.event(namespace=namespace)
async def message(sid, data):
    session_id = client_sessions.get(sid)
    if session_id:
        touch_session(session_id)


async def send_socket_io_message(msg, session_id: str | None = None):
    if session_id:
        try:
            await sio.emit("breath", msg, namespace=namespace, room=session_room(session_id))
        except Exception as e:
            logger.error(f"send socket_io session msg error:{e}")
        return

    if not client_ids:
        return
    try:
        await sio.emit("breath", msg, namespace=namespace)
    except Exception as e:
        logger.error(f"send socket_io msg error:{e}")


def set_snapshot_provider(provider: Callable[[], list[dict]] | None, session_id: str | None = None):
    if session_id:
        if provider is None:
            snapshot_providers.pop(session_id, None)
        else:
            snapshot_providers[session_id] = provider
        return

    global snapshot_provider
    snapshot_provider = provider


def remove_snapshot_provider(session_id: str):
    snapshot_providers.pop(session_id, None)


def set_session_touch_callback(callback: Callable[[str], None] | None):
    global session_touch_callback
    session_touch_callback = callback


def touch_session(session_id: str):
    if session_touch_callback is None:
        return
    try:
        session_touch_callback(session_id)
    except Exception as e:
        logger.error(f"touch session error:{e}")


def session_id_from_connect(environ, auth=None) -> str | None:
    candidates = []
    if isinstance(auth, dict):
        candidates.append(auth.get(SESSION_QUERY_PARAM))
        candidates.append(auth.get("sessionId"))
    query_string = environ.get("QUERY_STRING", "") if isinstance(environ, dict) else ""
    if query_string:
        query = parse_qs(query_string)
        candidates.extend(query.get(SESSION_QUERY_PARAM, []))
    for candidate in candidates:
        try:
            session_id = normalize_session_id(candidate)
        except ValueError:
            logger.warning("Ignoring invalid Socket.IO session id")
            return None
        if session_id:
            return session_id
    return None


async def send_recent_snapshot(sid, session_id: str | None = None):
    provider = snapshot_providers.get(session_id) if session_id else snapshot_provider
    if provider is None:
        return
    try:
        for message in provider():
            await sio.emit("breath", message, namespace=namespace, room=sid)
    except Exception as e:
        logger.error(f"send socket_io snapshot error:{e}")
