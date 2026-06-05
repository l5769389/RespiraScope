import asyncio

import ct_breath.socket_io_service as socket_io_service


def run(coro):
    return asyncio.run(coro)


def test_socket_io_broadcasts_to_all_connected_clients(monkeypatch):
    emitted = []

    async def fake_emit(event, data, namespace=None, room=None):
        emitted.append({
            "event": event,
            "data": data,
            "namespace": namespace,
            "room": room,
        })

    monkeypatch.setattr(socket_io_service.sio, "emit", fake_emit)
    socket_io_service.client_ids.clear()
    socket_io_service.client_sessions.clear()
    socket_io_service.set_snapshot_provider(None)

    run(socket_io_service.connect("monitor-client", {}))
    run(socket_io_service.connect("real-client", {}))
    run(socket_io_service.send_socket_io_message({"type": "raw", "data": [[1, 2]]}))

    assert socket_io_service.client_ids == {"monitor-client", "real-client"}
    assert emitted == [
        {
            "event": "breath",
            "data": {"type": "raw", "data": [[1, 2]]},
            "namespace": "/breath",
            "room": None,
        }
    ]

    run(socket_io_service.disconnect("monitor-client"))
    run(socket_io_service.disconnect("real-client"))


def test_socket_io_sends_recent_snapshot_to_new_client(monkeypatch):
    emitted = []

    async def fake_emit(event, data, namespace=None, room=None):
        emitted.append({
            "event": event,
            "data": data,
            "namespace": namespace,
            "room": room,
        })

    monkeypatch.setattr(socket_io_service.sio, "emit", fake_emit)
    socket_io_service.client_ids.clear()
    socket_io_service.client_sessions.clear()
    socket_io_service.set_snapshot_provider(lambda: [
        {"type": "raw", "data": [[10, 500]]},
        {"type": "peak", "data": [[12, 540]]},
    ])

    run(socket_io_service.connect("new-client", {}))

    assert emitted == [
        {
            "event": "breath",
            "data": {"type": "raw", "data": [[10, 500]]},
            "namespace": "/breath",
            "room": "new-client",
        },
        {
            "event": "breath",
            "data": {"type": "peak", "data": [[12, 540]]},
            "namespace": "/breath",
            "room": "new-client",
        },
    ]

    run(socket_io_service.disconnect("new-client"))
    socket_io_service.set_snapshot_provider(None)


def test_socket_io_routes_session_messages_to_session_room(monkeypatch):
    emitted = []
    rooms = []

    async def fake_emit(event, data, namespace=None, room=None):
        emitted.append({
            "event": event,
            "data": data,
            "namespace": namespace,
            "room": room,
        })

    async def fake_enter_room(sid, room, namespace=None):
        rooms.append({
            "sid": sid,
            "room": room,
            "namespace": namespace,
        })

    monkeypatch.setattr(socket_io_service.sio, "emit", fake_emit)
    monkeypatch.setattr(socket_io_service.sio, "enter_room", fake_enter_room)
    socket_io_service.client_ids.clear()
    socket_io_service.client_sessions.clear()
    socket_io_service.snapshot_providers.clear()
    socket_io_service.set_snapshot_provider(lambda: [{"type": "raw", "data": [[1, 2]]}], session_id="alpha")

    run(socket_io_service.connect("session-client", {"QUERY_STRING": "session_id=alpha"}))
    run(socket_io_service.send_socket_io_message({"type": "raw", "data": [[3, 4]]}, session_id="alpha"))

    assert rooms == [
        {
            "sid": "session-client",
            "room": "session:alpha",
            "namespace": "/breath",
        }
    ]
    assert emitted == [
        {
            "event": "breath",
            "data": {"type": "raw", "data": [[1, 2]]},
            "namespace": "/breath",
            "room": "session-client",
        },
        {
            "event": "breath",
            "data": {"type": "raw", "data": [[3, 4]]},
            "namespace": "/breath",
            "room": "session:alpha",
        },
    ]

    run(socket_io_service.disconnect("session-client"))
    socket_io_service.snapshot_providers.clear()
