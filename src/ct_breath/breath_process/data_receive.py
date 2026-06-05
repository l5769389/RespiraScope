import math
import time
import asyncio
from collections.abc import Callable

from ct_breath.breath_process.socket_client import AsyncSocketClient
from ct_breath.config import AppConfig, get_config
from ct_breath.mock_sensor.breath_simulator import BreathWaveform, MockBreathConfig
from ct_breath.time_utils import iso_time


class DataReceiver:
    def __init__(
        self,
        config: AppConfig | None = None,
        *,
        mock_config_provider: Callable[[], MockBreathConfig] | None = None,
        use_direct_mock: bool = False,
    ):
        config = config or get_config()
        self.sequence_number = 0
        self.socket_client = None
        self.data_handlers = []
        self.sensor_host = config.sensor_host
        self.sensor_port = config.sensor_port
        self.mock_config_provider = mock_config_provider
        self.use_direct_mock = use_direct_mock and mock_config_provider is not None
        self.running = False
        self.connected = False
        self.last_error: str | None = None
        self.last_connected_at: float | None = None
        self.last_disconnected_at: float | None = None
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
        if self.use_direct_mock:
            await self.start_direct_mock_receiving()
            return

        self.socket_client = AsyncSocketClient(
            host=self.sensor_host,
            port=self.sensor_port,
            message_callback=self.data_handler,
        )
        await self.socket_client.start_receiving()

    async def start_direct_mock_receiving(self):
        self.running = True
        self.connected = True
        self.last_error = None
        self.last_connected_at = time.time()
        waveform = BreathWaveform(self.mock_config_provider)
        start_time = time.time_ns()

        try:
            while self.running:
                config = self.mock_config_provider()
                current_time = time.time_ns()
                elapsed_sec = (current_time - start_time) / 1_000_000_000
                value = waveform.value_at(elapsed_sec)
                self.data_handler(value)

                interval_ms = max(1, config.sample_interval_ms)
                elapsed_ms = elapsed_sec * 1000
                next_send_time_ms = math.ceil(elapsed_ms / interval_ms) * interval_ms
                next_send_time_ns = start_time + int(next_send_time_ms * 1_000_000)
                delay_seconds = max(0, (next_send_time_ns - current_time) / 1_000_000_000)
                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)
        except Exception as exc:
            self.last_error = str(exc)
            raise
        finally:
            self.connected = False
            self.last_disconnected_at = time.time()
            self.running = False

    async def stop_receiving(self):
        self.running = False
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
        socket_status = self.socket_client.status() if self.socket_client else self._local_status(now)
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

    def _local_status(self, now: float) -> dict:
        source_host = "direct-mock" if self.use_direct_mock else self.sensor_host
        source_port = 0 if self.use_direct_mock else self.sensor_port
        return {
            "host": source_host,
            "port": source_port,
            "running": self.running,
            "connected": self.connected,
            "received_count": self.received_count,
            "last_error": self.last_error,
            "last_connected_at": iso_time(self.last_connected_at),
            "last_disconnected_at": iso_time(self.last_disconnected_at),
            "last_received_at": iso_time(self.last_data_at),
            "seconds_since_last_data": (
                round(now - self.last_data_at, 3)
                if self.last_data_at is not None
                else None
            ),
        }

