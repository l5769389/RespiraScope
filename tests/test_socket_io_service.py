import asyncio

from ct_breath import socket_io_service


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
