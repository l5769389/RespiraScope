import asyncio
from asyncio import Queue
from collections import deque

from ct_breath.logger import logger


RECENT_WAVE_POINTS = 2000
RECENT_MARKER_POINTS = 300
RECENT_STATUS_EVENTS = 20


class DataQueueManager:
    def __init__(self):
        self.raw_data_queue = Queue(maxsize=1000)
        self.filter_data_queue = Queue(maxsize=1000)
        self.peak_queue = Queue(maxsize=100)
        self.valley_queue = Queue(maxsize=100)
        self.metrics_queue = Queue(maxsize=100)
        self.signal_quality_queue = Queue(maxsize=100)
        self.dropped_counts = {
            "raw": 0,
            "filtered": 0,
            "peaks": 0,
            "valleys": 0,
            "metrics": 0,
            "signal_quality": 0,
        }
        self.high_watermarks = {
            "raw": 0,
            "filtered": 0,
            "peaks": 0,
            "valleys": 0,
            "metrics": 0,
            "signal_quality": 0,
        }
        self.recent_raw = deque(maxlen=RECENT_WAVE_POINTS)
        self.recent_filtered = deque(maxlen=RECENT_WAVE_POINTS)
        self.recent_peaks = deque(maxlen=RECENT_MARKER_POINTS)
        self.recent_valleys = deque(maxlen=RECENT_MARKER_POINTS)
        self.recent_metrics = deque(maxlen=RECENT_STATUS_EVENTS)
        self.recent_signal_quality = deque(maxlen=RECENT_STATUS_EVENTS)

    def handle_data(self, sequence_number, sensor_val):
        point = [sequence_number, sensor_val]
        self.recent_raw.append(point)
        try:
            self.raw_data_queue.put_nowait(point)
            self._track_high_watermark("raw", self.raw_data_queue)
        except asyncio.QueueFull:
            self.dropped_counts["raw"] += 1
            logger.warning("Raw data queue full")

    def handle_filtered_data(self, sequences, values):
        for seq, val in zip(sequences, values):
            point = [seq, val]
            self.recent_filtered.append(point)
            try:
                self.filter_data_queue.put_nowait(point)
                self._track_high_watermark("filtered", self.filter_data_queue)
            except asyncio.QueueFull:
                self.dropped_counts["filtered"] += 1
                logger.warning("Filter data queue full")

    def handle_peak(self, peak_data):
        point = self._marker_point(peak_data)
        self.recent_peaks.append(point)
        try:
            self.peak_queue.put_nowait(point)
            self._track_high_watermark("peaks", self.peak_queue)
        except asyncio.QueueFull:
            self.dropped_counts["peaks"] += 1
            logger.warning("Peak data queue full")

    def handle_valley(self, valley_data):
        point = self._marker_point(valley_data)
        self.recent_valleys.append(point)
        try:
            self.valley_queue.put_nowait(point)
            self._track_high_watermark("valleys", self.valley_queue)
        except asyncio.QueueFull:
            self.dropped_counts["valleys"] += 1
            logger.warning("Valley data queue full")

    def handle_metrics(self, metrics):
        self.recent_metrics.append(metrics)
        try:
            self.metrics_queue.put_nowait(metrics)
            self._track_high_watermark("metrics", self.metrics_queue)
        except asyncio.QueueFull:
            self.dropped_counts["metrics"] += 1
            logger.warning("Metrics queue full")

    def handle_signal_quality(self, event):
        self.recent_signal_quality.append(event)
        try:
            self.signal_quality_queue.put_nowait(event)
            self._track_high_watermark("signal_quality", self.signal_quality_queue)
        except asyncio.QueueFull:
            self.dropped_counts["signal_quality"] += 1
            logger.warning("Signal quality queue full")

    def snapshot_messages(self) -> list[dict]:
        raw = list(self.recent_raw)
        filtered = list(self.recent_filtered)
        min_sequence = self._snapshot_min_sequence(raw, filtered)
        peaks = self._markers_since(self.recent_peaks, min_sequence)
        valleys = self._markers_since(self.recent_valleys, min_sequence)
        metrics = list(self.recent_metrics)
        signal_quality = list(self.recent_signal_quality)

        messages = []
        for item_type, data in (
            ("raw", raw),
            ("filtered", filtered),
            ("peak", peaks),
            ("valley", valleys),
            ("metrics", metrics),
            ("signal_quality", signal_quality),
        ):
            if data:
                messages.append({"type": item_type, "data": data})
        return messages

    def status(self) -> dict:
        return {
            "sizes": {
                "raw": self.raw_data_queue.qsize(),
                "filtered": self.filter_data_queue.qsize(),
                "peaks": self.peak_queue.qsize(),
                "valleys": self.valley_queue.qsize(),
                "metrics": self.metrics_queue.qsize(),
                "signal_quality": self.signal_quality_queue.qsize(),
            },
            "dropped": dict(self.dropped_counts),
            "high_watermark": dict(self.high_watermarks),
        }

    def _marker_point(self, marker_data):
        if isinstance(marker_data, dict):
            return [marker_data["sequence"], marker_data["value"]]
        return list(marker_data)

    def _snapshot_min_sequence(self, raw, filtered):
        candidates = []
        if raw:
            candidates.append(raw[0][0])
        if filtered:
            candidates.append(filtered[0][0])
        return min(candidates) if candidates else None

    def _markers_since(self, markers, min_sequence):
        if min_sequence is None:
            return list(markers)
        return [point for point in markers if point[0] >= min_sequence]

    def _track_high_watermark(self, queue_name: str, queue: Queue):
        self.high_watermarks[queue_name] = max(
            self.high_watermarks[queue_name],
            queue.qsize(),
        )
