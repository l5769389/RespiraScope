import asyncio
from collections import deque
from typing import List

from ct_breath.breath_process.filter_strategies import (
    FILTER_STARTUP_DELAY,
    OfflineFilterStrategy,
    RealtimeFilterStrategy,
    butterworth_filter,
    gaussian_smooth,
)
from ct_breath.http.schemas import FilterConfig
from ct_breath.logger import logger


class SignalProcessor:
    def __init__(
        self,
        window_size=2000,
        step_size=5,
        realtime_strategy=None,
        offline_strategy=None,
    ):
        self.window_size = window_size
        self.step_size = step_size
        self.realtime_strategy = realtime_strategy or RealtimeFilterStrategy()
        self.offline_strategy = offline_strategy or OfflineFilterStrategy()

        self.history_buffer = []
        self.history_sequence = []
        self.new_data_buffer = deque(maxlen=window_size)
        self.new_sequence_buffer = deque(maxlen=window_size)
        self.filter_buffer = deque()
        self.filter_config = FilterConfig()
        self.output_handlers = []

    def add_output_handler(self, handler):
        self.output_handlers.append(handler)

    def handle_data(self, sequence_number, sensor_val):
        self.new_data_buffer.append(sensor_val)
        self.new_sequence_buffer.append(sequence_number)

    def update_filter_config(self, config: FilterConfig):
        self.filter_config = config
        self.history_buffer.clear()
        self.history_sequence.clear()
        self.new_data_buffer.clear()
        self.new_sequence_buffer.clear()

    async def start_processing(self):
        while True:
            await asyncio.sleep(0.04)
            if len(self.new_data_buffer) >= self.step_size:
                await self.process_sliding_window()

    async def process_sliding_window(self):
        current_new_data = []
        current_new_seq = []
        for _ in range(self.step_size):
            current_new_data.append(self.new_data_buffer.popleft())
            current_new_seq.append(self.new_sequence_buffer.popleft())

        combined_data = self.history_buffer + current_new_data
        combined_seq = self.history_sequence + current_new_seq
        filtered_data, filtered_seq = await self.apply_realtime_filter(combined_data, combined_seq)
        if filtered_data is not None:
            new_filtered_data = list(filtered_data[-self.step_size:])
            new_filtered_seq = filtered_seq[-self.step_size:]
            for handler in self.output_handlers:
                try:
                    handler.handle_filtered_data(new_filtered_seq, new_filtered_data)
                except Exception as exc:
                    logger.error("filtered data handler error: %s", exc)

        history_keep_size = min(self.window_size - self.step_size, len(combined_data))
        self.history_buffer = combined_data[-history_keep_size:]
        self.history_sequence = combined_seq[-history_keep_size:]

    async def apply_realtime_filter(self, data_to_process, sequence_nums):
        return await self._apply_strategy(self.realtime_strategy, data_to_process, sequence_nums)

    async def apply_offline_filter(self, data_to_process, sequence_nums):
        return await self._apply_strategy(self.offline_strategy, data_to_process, sequence_nums)

    async def apply_filters(self, data_to_process, sequence_nums, rt=False):
        if rt:
            return await self.apply_realtime_filter(data_to_process, sequence_nums)
        return await self.apply_offline_filter(data_to_process, sequence_nums)

    async def _apply_strategy(self, strategy, data_to_process, sequence_nums):
        try:
            return strategy.filter(data_to_process, sequence_nums, self.filter_config)
        except Exception as e:
            logger.error(f"filter error,{e}")
            return None, None

    async def filter_data(self, raw_data_list: List[List[int]]):
        raw_data = [item[1] for item in raw_data_list]
        raw_sequence = [item[0] for item in raw_data_list]
        self.filter_buffer.clear()
        filtered_data, filtered_seq = await self.apply_offline_filter(raw_data, raw_sequence)
        if filtered_data is not None:
            for seq, val in zip(filtered_seq, filtered_data):
                self.filter_buffer.append([seq, val])
            return filtered_data, filtered_seq, list(self.filter_buffer)

        logger.error("raw data is too short")
        return None, None, None
