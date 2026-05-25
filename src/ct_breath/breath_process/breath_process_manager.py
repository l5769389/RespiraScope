import asyncio

from ct_breath.breath_process.data_manager import DataQueueManager
from ct_breath.breath_process.data_receive import DataReceiver
from ct_breath.breath_process.peak_valley_detector import (
    BreathRateCalculator,
    PeakValleyDetector,
    PeakValleyHandler,
)
from ct_breath.breath_process.filter_strategies import FILTER_STARTUP_DELAY
from ct_breath.breath_process.record_manager import RecordManager
from ct_breath.breath_process.send_to_client import DataSender
from ct_breath.breath_process.signal_processor import SignalProcessor
from ct_breath.breath_process.signal_quality import SignalQualityAnalyzer
from ct_breath.config import get_config
from ct_breath.http.schemas import ApplyFilterConfig, FilterConfig
from ct_breath.logger import logger
from ct_breath.socket_io_service import set_snapshot_provider


class BreathProcessSystem:
    def __init__(self):
        config = get_config()
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
            buffer_size=1000,
        )
        self.signal_quality_analyzer = SignalQualityAnalyzer(
            sampling_rate=self.signal_processor.filter_config.sampling_rate,
        )
        self.peak_valley_handler = PeakValleyHandler(self.queue_manager)
        self.breath_rate_calculator = BreathRateCalculator()
        self.is_start = False
        self.state = "idle"
        self.last_error: str | None = None
        self.tasks: dict[str, asyncio.Task] = {}
        set_snapshot_provider(self.queue_manager.snapshot_messages)
        self._setup_connections()
        self._sync_detection_config(self.signal_processor.filter_config)

    def _setup_connections(self):
        self.peak_valley_detector.add_output_handler(self.peak_valley_handler)
        self.peak_valley_detector.add_output_handler(self.record_manager)
        self.signal_quality_analyzer.add_output_handler(self.queue_manager)
        self.signal_processor.add_output_handler(self.queue_manager)
        self.signal_processor.add_output_handler(self.record_manager)
        self.signal_processor.add_output_handler(self.peak_valley_detector)

    def start(self, config: FilterConfig):
        if self.is_start and self.state == "running":
            return self.status()

        self.is_start = True
        self.state = "running"
        self.last_error = None
        self.signal_processor.update_filter_config(config)
        self._sync_detection_config(config)
        self._attach_receiver_handlers()
        self._ensure_receiver_task()
        return self.status()

    async def stop(self):
        self.is_start = False
        self.state = "stopped"
        self.data_receiver.clear_data_handlers()
        self.signal_processor.history_buffer.clear()
        self.signal_processor.history_sequence.clear()
        self.signal_processor.new_data_buffer.clear()
        self.signal_processor.new_sequence_buffer.clear()
        self.peak_valley_detector.clear_history()
        self.signal_quality_analyzer.clear_history()
        await self.data_receiver.stop_receiving()
        self._cancel_task("receiver")

    async def stop_system(self):
        await self.stop()
        for task_name in list(self.tasks):
            self._cancel_task(task_name)

    def end(self):
        self.is_start = False
        self.state = "stopped"
        self.data_receiver.clear_data_handlers()

    def start_record(self):
        if self.record_manager.recording:
            return self.record_manager.status()
        if not self.is_start or self.state != "running":
            raise ValueError("Receive has not been started")
        if self.record_manager.latest_raw_sequence is None:
            raise ValueError("No raw data has been received")
        return self.record_manager.start_record()

    def stop_record(self):
        self.record_manager.stop_record()

    def reset_record(self):
        return self.record_manager.reset_record()

    async def stop_record_and_filter(self, post_timeout_seconds: float = 10.0):
        if self.record_manager.record_start_time is None:
            raise ValueError("No recording has been started")
        if self.record_manager.recording:
            self.record_manager.stop_record()

        await self._wait_for_post_record_padding(post_timeout_seconds)
        if not self.record_manager.raw_record_queue:
            raise ValueError("No record data is available")

        raw_points = self.record_manager.raw_points_for_filter()
        filtered_data, peak, valley, metrics, filter_status = await self._offline_filter_points(
            raw_points,
            self.signal_processor.filter_config,
        )
        record_data = self.record_manager.build_record_data(
            self.signal_processor.filter_config,
            filtered_data=filtered_data,
            peak_data=peak,
            valley_data=valley,
            metrics=metrics,
            filter_status=filter_status,
        )
        return record_data

    def save_record(self, folder_path):
        return self.record_manager.save_record(self.signal_processor.filter_config, folder_path)

    def start_scan(self):
        return self.record_manager.start_scan()

    def stop_scan(self):
        return self.record_manager.stop_scan()

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

    def status(self) -> dict:
        queue_status = self.queue_manager.status()
        return {
            "started": self.is_start,
            "state": self.state,
            "last_error": self.last_error,
            "tasks": {
                name: {
                    "done": task.done(),
                    "cancelled": task.cancelled(),
                }
                for name, task in self.tasks.items()
            },
            "receiver": self.data_receiver.status(),
            "queues": queue_status["sizes"],
            "queue_stats": {
                "dropped": queue_status["dropped"],
                "high_watermark": queue_status["high_watermark"],
            },
            "record": self.record_manager.status(),
            "signal_quality": self.signal_quality_analyzer.status(),
            "filter_config": self.signal_processor.filter_config.model_dump(),
        }

    async def start_system(self):
        self._ensure_processing_tasks()
        try:
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        except Exception as exc:
            self.state = "error"
            self.last_error = str(exc)
            logger.error("Error in breath system: %s", exc)
        finally:
            for task_name in list(self.tasks):
                self._cancel_task(task_name)

    def _attach_receiver_handlers(self):
        self.data_receiver.add_data_handler(self.queue_manager)
        self.data_receiver.add_data_handler(self.record_manager)
        self.data_receiver.add_data_handler(self.signal_quality_analyzer)
        self.data_receiver.add_data_handler(self.signal_processor)

    def _sync_detection_config(self, config: FilterConfig):
        self.peak_valley_detector.update_from_filter_config(config)
        self.signal_quality_analyzer.update_sampling_rate(config.sampling_rate)

    async def _wait_for_post_record_padding(self, timeout_seconds: float):
        if not self.record_manager.post_recording:
            return

        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.0, float(timeout_seconds))
        while self.record_manager.post_recording and loop.time() < deadline:
            await asyncio.sleep(0.04)

    async def _offline_filter_points(self, raw_points, filter_config: FilterConfig):
        detector = PeakValleyDetector()
        detector.update_from_filter_config(filter_config)
        if not raw_points:
            return [], [], [], detector.calculate_metrics([]), "no_data"

        filtered_data = []
        peak = []
        valley = []
        for raw_segment in self._continuous_raw_segments(raw_points, filter_config.data_gap_reset_points):
            if len(raw_segment) < FILTER_STARTUP_DELAY:
                continue

            processor = SignalProcessor()
            processor.update_filter_config(filter_config)
            segment_filtered, segment_sequences, segment_payload = await processor.filter_data(raw_segment)
            if segment_filtered is None or segment_sequences is None or not segment_payload:
                continue

            filtered_data.extend(segment_payload)
            segment_peak, segment_valley = detector.detect_peak_valley_batch(
                segment_filtered,
                segment_sequences,
            )
            peak.extend(segment_peak)
            valley.extend(segment_valley)

        if not filtered_data:
            return [], [], [], detector.calculate_metrics([]), "too_short"

        peak = sorted(peak, key=lambda item: item["sequence"])
        valley = sorted(valley, key=lambda item: item["sequence"])
        metrics = detector.calculate_metrics(peak)
        return filtered_data, peak, valley, metrics, "offline"

    def _continuous_raw_segments(self, raw_points, gap_threshold):
        if not raw_points:
            return []

        threshold = max(1, int(gap_threshold))
        segments = []
        current = [raw_points[0]]
        previous_sequence = int(raw_points[0][0])
        for point in raw_points[1:]:
            sequence = int(point[0])
            if sequence - previous_sequence > threshold:
                segments.append(current)
                current = []
            current.append(point)
            previous_sequence = sequence

        if current:
            segments.append(current)
        return segments

    def _ensure_processing_tasks(self):
        self._ensure_task("processor", self.signal_processor.start_processing)
        self._ensure_task("sender", self.data_sender.start_sending)

    def _ensure_receiver_task(self):
        self._ensure_task("receiver", self.data_receiver.start_receiving)

    def _ensure_task(self, name: str, coro_factory):
        task = self.tasks.get(name)
        if task is not None and not task.done():
            return
        try:
            self.tasks[name] = asyncio.create_task(coro_factory())
        except RuntimeError:
            logger.debug("No running loop available to start %s task", name)

    def _cancel_task(self, name: str):
        task = self.tasks.pop(name, None)
        if task is not None and not task.done():
            task.cancel()


breath_system = BreathProcessSystem()
