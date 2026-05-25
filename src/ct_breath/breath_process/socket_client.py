import asyncio
import time
from typing import Callable, Optional

from ct_breath.time_utils import iso_time


class AsyncSocketClient:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8088,
        message_callback: Optional[Callable[[int], None]] = None,
    ):
        self.host = host
        self.port = port
        self.message_callback = message_callback
        self.running = False
        self.connected = False
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.reconnect_delay = 5
        self.last_error: str | None = None
        self.last_connected_at: float | None = None
        self.last_disconnected_at: float | None = None
        self.last_received_at: float | None = None
        self.received_count = 0

    async def connect(self):
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host,
                self.port,
            )
            print(f"Connected to server {self.host}:{self.port}")
            self.connected = True
            self.last_error = None
            self.last_connected_at = time.time()
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            self.connected = False
            self.last_error = str(e)
            return False

    async def start_receiving(self):
        self.running = True
        while self.running:
            try:
                if not await self.connect():
                    if not self.running:
                        break
                    print(f"Failed to connect, retrying in {self.reconnect_delay} seconds...")
                    await asyncio.sleep(self.reconnect_delay)
                    continue

                while self.running:
                    try:
                        data = await self.reader.read(4)
                        if not data or len(data) < 4:
                            print("Server closed connection or incomplete data")
                            break

                        high_byte = data[2]
                        low_byte = data[3]
                        value = high_byte * 256 + low_byte
                        self.last_received_at = time.time()
                        self.received_count += 1

                        if self.message_callback:
                            self.message_callback(value)
                    except asyncio.CancelledError:
                        print("Socket client task cancelled")
                        break
                    except Exception as e:
                        print(f"Receive error: {e}")
                        self.last_error = str(e)
                        break

            except asyncio.CancelledError:
                print("Socket client cancelled")
                break
            except Exception as e:
                print(f"Connection error: {e}")
                self.last_error = str(e)

            finally:
                await self.disconnect()

            if not self.running:
                break

            print(f"Reconnecting in {self.reconnect_delay} seconds...")
            await asyncio.sleep(self.reconnect_delay)

    async def disconnect(self):
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
                print("Disconnected from server")
            except Exception as e:
                print(f"Disconnect error: {e}")
                self.last_error = str(e)
        self.connected = False
        self.last_disconnected_at = time.time()
        self.reader = None
        self.writer = None

    def stop(self):
        self.running = False

    def status(self) -> dict:
        now = time.time()
        return {
            "host": self.host,
            "port": self.port,
            "running": self.running,
            "connected": self.connected,
            "received_count": self.received_count,
            "last_error": self.last_error,
            "last_connected_at": iso_time(self.last_connected_at),
            "last_disconnected_at": iso_time(self.last_disconnected_at),
            "last_received_at": iso_time(self.last_received_at),
            "seconds_since_last_data": (
                round(now - self.last_received_at, 3)
                if self.last_received_at is not None
                else None
            ),
        }
