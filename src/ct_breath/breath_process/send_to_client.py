import asyncio

from ct_breath.breath_process.data_manager import DataQueueManager
from ct_breath.socket_io_service import send_socket_io_message
from asyncio import Queue


async def send_type_data(type, queue: Queue):
    batch = []
    while not queue.empty():
        try:
            data = queue.get_nowait()
            batch.append(data)
        except asyncio.QueueEmpty:
            break
    if len(batch) > 0:
        await send_socket_io_message({
            'type': type,
            'data': batch
        })


# 5. 数据发送管理器
class DataSender:
    def __init__(self, queue_manager: DataQueueManager, send_interval=0.04):
        self.queue_manager = queue_manager
        self.send_interval = send_interval

    async def start_sending(self):
        """开始批量发送数据"""
        while True:
            await asyncio.sleep(self.send_interval)
            await send_type_data('raw', self.queue_manager.raw_data_queue)
            await send_type_data('filtered', self.queue_manager.filter_data_queue)
            await send_type_data('peak', self.queue_manager.peak_queue)
            await send_type_data('valley', self.queue_manager.valley_queue)
            await send_type_data('metrics', self.queue_manager.metrics_queue)
