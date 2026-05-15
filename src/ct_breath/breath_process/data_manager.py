import asyncio
from asyncio import Queue

from ct_breath.logger import logger

# 3. 数据队列管理器
class DataQueueManager:
    def __init__(self):
        self.raw_data_queue = Queue(maxsize=1000)
        self.filter_data_queue = Queue(maxsize=1000)
        self.peak_queue = Queue(maxsize=100)
        self.valley_queue = Queue(maxsize=100)
        self.metrics_queue = Queue(maxsize=100)

    def handle_data(self, sequence_number, sensor_val):
        """处理原始数据"""
        try:
            self.raw_data_queue.put_nowait([sequence_number, sensor_val])
        except asyncio.QueueFull:
            logger.warning("Raw data queue full")

    def handle_filtered_data(self, sequences, values):
        """处理滤波后的数据"""
        for seq, val in zip(sequences, values):
            try:
                self.filter_data_queue.put_nowait([seq, val])
            except asyncio.QueueFull:
                logger.warning("Filter data queue full")

    def handle_metrics(self, metrics):
        try:
            self.metrics_queue.put_nowait(metrics)
        except asyncio.QueueFull:
            logger.warning("Metrics queue full")
