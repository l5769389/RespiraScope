import time

from ct_breath.breath_process.socket_client import AsyncSocketClient
from ct_breath.config import get_config
from ct_breath.time_utils import iso_time


class DataReceiver:
    def __init__(self):
        config = get_config()
        self.sequence_number = 0
        self.socket_client = None
        self.data_handlers = []
        self.sensor_host = config.sensor_host
        self.sensor_port = config.sensor_port
        self.last_data_at = None
        self.received_count = 0

    def add_data_handler(self, handler):
        if handler not in self.data_handlers:
            self.data_handlers.append(handler)

    def data_handler(self, sensor_val):
        self.last_data_at = time.time()
        self.received_count += 1
        for handler in self.data_handlers:
            handler.handle_data(self.sequence_number, sensor_val)
        self.sequence_number += 1

    async def start_receiving(self):
        self.socket_client = AsyncSocketClient(
            host=self.sensor_host,
            port=self.sensor_port,
            message_callback=self.data_handler,
        )
        await self.socket_client.start_receiving()

    async def stop_receiving(self):
        if self.socket_client:
            self.socket_client.stop()
            await self.socket_client.disconnect()

    def remove_data_handler(self, handler):
        if handler in self.data_handlers:
            self.data_handlers.remove(handler)

    def clear_data_handlers(self):
        self.data_handlers.clear()

    def status(self) -> dict:
        now = time.time()
        socket_status = self.socket_client.status() if self.socket_client else {
            "host": self.sensor_host,
            "port": self.sensor_port,
            "running": False,
            "connected": False,
            "received_count": 0,
            "last_error": None,
            "last_connected_at": None,
            "last_disconnected_at": None,
            "last_received_at": None,
            "seconds_since_last_data": None,
        }
        return {
            "sensor_host": self.sensor_host,
            "sensor_port": self.sensor_port,
            "sequence_number": self.sequence_number,
            "received_count": self.received_count,
            "last_data_at": iso_time(self.last_data_at),
            "seconds_since_last_data": (
                round(now - self.last_data_at, 3)
                if self.last_data_at is not None
                else None
            ),
            "socket": socket_status,
        }
