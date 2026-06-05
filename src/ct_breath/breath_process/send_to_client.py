import asyncio
from asyncio import Queue
from collections.abc import Awaitable, Callable

from ct_breath.breath_process.data_manager import DataQueueManager
from ct_breath.socket_io_service import send_socket_io_message


MessageSender = Callable[[dict], Awaitable[None]]


async def send_type_data(
    data_type: str,
    queue: Queue,
    send_message: MessageSender = send_socket_io_message,
):
    batch = []
    while not queue.empty():
        try:
            data = queue.get_nowait()
            batch.append(data)
        except asyncio.QueueEmpty:
            break
    if batch:
        await send_message({
            "type": data_type,
            "data": batch,
        })


class DataSender:
    def __init__(
        self,
        queue_manager: DataQueueManager,
        send_interval=0.04,
        send_message: MessageSender = send_socket_io_message,
    ):
        self.queue_manager = queue_manager
        self.send_interval = send_interval
        self.send_message = send_message

    async def start_sending(self):
        while True:
            await asyncio.sleep(self.send_interval)
            await send_type_data("raw", self.queue_manager.raw_data_queue, self.send_message)
            await send_type_data("filtered", self.queue_manager.filter_data_queue, self.send_message)
            await send_type_data("peak", self.queue_manager.peak_queue, self.send_message)
            await send_type_data("valley", self.queue_manager.valley_queue, self.send_message)
            await send_type_data("metrics", self.queue_manager.metrics_queue, self.send_message)
            await send_type_data("signal_quality", self.queue_manager.signal_quality_queue, self.send_message)
