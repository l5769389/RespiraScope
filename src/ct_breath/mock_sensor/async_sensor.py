import asyncio
import math
import time
from typing import Set

from ct_breath.config import AppConfig, get_config
from ct_breath.logger import logger
from ct_breath.mock_sensor.breath_simulator import mock_breath_controller


def encode_sensor_value(value: int) -> bytearray:
    value = max(0, min(65535, int(value)))
    buffer = bytearray(4)
    buffer[2] = value // 256
    buffer[3] = value % 256
    return buffer


class AsyncSimulateSensor:
    def __init__(self, config: AppConfig | None = None):
        self.config = config or get_config()
        self.host = self.config.mock_signal_bind_host
        self.port = self.config.sensor_port
        self.server = None
        self.running = False
        self.stopped = False
        self.clients: Set[asyncio.StreamWriter] = set()
        self.client_tasks: Set[asyncio.Task] = set()

    async def start(self):
        self.running = True
        self.stopped = False

        try:
            self.server = await asyncio.start_server(
                self.handle_client,
                self.host,
                self.port,
            )

            logger.info("Mock TCP signal server listening on %s:%s", self.host, self.port)

            async with self.server:
                await self.server.serve_forever()

        except Exception as e:
            logger.warning("Mock TCP signal server stopped: %s", e)
        finally:
            await self.stop()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        client_address = writer.get_extra_info("peername")
        logger.debug("Mock TCP client connected from %s", client_address)

        self.clients.add(writer)
        signal_task = asyncio.create_task(self.send_signal_loop(writer))
        self.client_tasks.add(signal_task)

        try:
            while self.running:
                try:
                    data = await asyncio.wait_for(reader.read(1024), timeout=1.0)
                    if not data:
                        break
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.debug("Mock TCP client read failed: %s", e)
                    break

        except Exception as e:
            logger.debug("Mock TCP client handler failed: %s", e)
        finally:
            await self.disconnect_client(writer, signal_task)

    async def send_signal_loop(self, writer: asyncio.StreamWriter):
        waveform = mock_breath_controller.create_waveform()
        start_time = time.time_ns()

        while self.running:
            try:
                if writer.is_closing():
                    break

                config = mock_breath_controller.get_config()
                current_time = time.time_ns()
                elapsed_sec = (current_time - start_time) / 1_000_000_000
                value = waveform.value_at(elapsed_sec)

                writer.write(encode_sensor_value(value))
                await writer.drain()

                interval_ms = max(1, config.sample_interval_ms)
                elapsed_ms = elapsed_sec * 1000
                next_send_time_ms = math.ceil(elapsed_ms / interval_ms) * interval_ms
                next_send_time_ns = start_time + int(next_send_time_ms * 1_000_000)
                delay_seconds = max(0, (next_send_time_ns - current_time) / 1_000_000_000)

                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)

            except Exception as e:
                logger.debug("Mock TCP signal send failed: %s", e)
                break

    async def disconnect_client(self, writer: asyncio.StreamWriter, signal_task: asyncio.Task):
        if writer in self.clients:
            self.clients.remove(writer)

        if signal_task in self.client_tasks:
            self.client_tasks.remove(signal_task)
            signal_task.cancel()

        try:
            writer.close()
            await writer.wait_closed()
            logger.debug("Mock TCP client disconnected")
        except Exception as e:
            logger.debug("Mock TCP client close failed: %s", e)

    async def stop(self):
        if self.stopped:
            return
        self.stopped = True
        should_log = self.running or self.server is not None or bool(self.clients)
        self.running = False

        for task in list(self.client_tasks):
            task.cancel()

        for writer in list(self.clients):
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as e:
                logger.debug("Mock TCP client close failed: %s", e)

        self.clients.clear()
        self.client_tasks.clear()

        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

        if should_log:
            logger.info("Mock TCP signal server stopped")


async def async_sensor_start(config: AppConfig | None = None):
    simulate_sensor = AsyncSimulateSensor(config)
    await simulate_sensor.start()
