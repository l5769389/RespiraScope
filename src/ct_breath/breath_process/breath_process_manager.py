import asyncio
from ct_breath.breath_process.data_receive import DataReceiver
from ct_breath.breath_process.data_manager import DataQueueManager
from ct_breath.breath_process.peak_valley_detector import PeakValleyDetector, PeakValleyHandler, \
    BreathRateCalculator
from ct_breath.breath_process.record_manager import RecordManager
from ct_breath.breath_process.send_to_client import  DataSender
from ct_breath.breath_process.signal_processor import SignalProcessor
from ct_breath.config import get_config
from ct_breath.http.schemas import ApplyFilterConfig, FilterConfig
from ct_breath.logger import logger


# 6. 主协调器
class BreathProcessSystem:
    def __init__(self):
        config = get_config()
        # 初始化各个组件
        self.data_receiver = DataReceiver()
        self.signal_processor = SignalProcessor()
        self.queue_manager = DataQueueManager()
        self.record_manager = RecordManager(
            pre_points=config.record_pre_points,
            post_points=config.record_post_points,
        )
        self.data_sender = DataSender(self.queue_manager)
        self.peak_valley_detector = PeakValleyDetector(
            min_peak_height=None,
            min_peak_distance=25,
            min_valley_distance=25,
            prominence=3.0,
            buffer_size=1000
        )

        self.peak_valley_handler = PeakValleyHandler(self.queue_manager)
        self.breath_rate_calculator = BreathRateCalculator()
        self.is_start = False
        # 建立组件间的连接
        self._setup_connections()
        self._sync_detection_config(self.signal_processor.filter_config)

    def _setup_connections(self):
        if self.is_start:
            self.data_receiver.add_data_handler(self.queue_manager)
            self.data_receiver.add_data_handler(self.record_manager)
            self.data_receiver.add_data_handler(self.signal_processor)

        self.peak_valley_detector.add_output_handler(self.peak_valley_handler)
        self.peak_valley_detector.add_output_handler(self.record_manager)

        # 信号处理器连接到队列管理器和记录管理器
        self.signal_processor.add_output_handler(self.queue_manager)
        self.signal_processor.add_output_handler(self.record_manager)
        self.signal_processor.add_output_handler(self.peak_valley_detector)

    def start(self, config: FilterConfig):
        self.is_start = True
        self.signal_processor.update_filter_config(config)
        self._sync_detection_config(config)
        self.data_receiver.add_data_handler(self.queue_manager)
        self.data_receiver.add_data_handler(self.record_manager)
        self.data_receiver.add_data_handler(self.signal_processor)

    def end(self):
        pass

    def start_record(self):
        self.record_manager.start_record()

    def stop_record(self):
        self.record_manager.stop_record()

    def save_record(self, folder_path):
        return self.record_manager.save_record(self.signal_processor.filter_config, folder_path, )

    def update_filter_config(self, config: FilterConfig):
        self.signal_processor.update_filter_config(config)
        self._sync_detection_config(config)

    async def apply_filter(self, config: ApplyFilterConfig):
        offline_processor = SignalProcessor()
        offline_processor.update_filter_config(config.filter_config)
        offline_detector = PeakValleyDetector()
        offline_detector.update_from_filter_config(config.filter_config)
        if not config.raw_data:
            return [], [], [], offline_processor.filter_config.model_dump(), offline_detector.calculate_metrics([])
        filtered_data, filtered_seq, list_filter_data = await offline_processor.filter_data(config.raw_data)
        peak, valley = offline_detector.detect_peak_valley_batch(filtered_data, filtered_seq)
        metrics = offline_detector.calculate_metrics(peak)
        return list_filter_data, peak, valley, offline_processor.filter_config.model_dump(), metrics

    def _sync_detection_config(self, config: FilterConfig):
        self.peak_valley_detector.update_from_filter_config(config)

    def status(self) -> dict:
        return {
            "started": self.is_start,
            "receiver": self.data_receiver.status(),
            "queues": {
                "raw": self.queue_manager.raw_data_queue.qsize(),
                "filtered": self.queue_manager.filter_data_queue.qsize(),
                "peaks": self.queue_manager.peak_queue.qsize(),
                "valleys": self.queue_manager.valley_queue.qsize(),
                "metrics": self.queue_manager.metrics_queue.qsize(),
            },
            "record": {
                "pre_points": self.record_manager.pre_points,
                "post_points": self.record_manager.post_points,
                "recording": self.record_manager.recording,
                "post_recording": self.record_manager.post_recording,
                "record_complete": self.record_manager.record_complete,
                "record_start_sequence": self.record_manager.record_start_sequence,
                "record_end_sequence": self.record_manager.record_end_sequence,
                "capture_start_sequence": self.record_manager.capture_start_sequence,
                "capture_end_sequence": self.record_manager.capture_end_sequence,
            },
            "filter_config": self.signal_processor.filter_config.model_dump(),
        }

    async def start_system(self):
        tasks = [
            asyncio.create_task(self.data_receiver.start_receiving()),
            asyncio.create_task(self.signal_processor.start_processing()),
            asyncio.create_task(self.data_sender.start_sending())
        ]

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error in breath system: {e}")
        finally:
            # 清理任务
            for task in tasks:
                if not task.done():
                    task.cancel()

breath_system = BreathProcessSystem()
