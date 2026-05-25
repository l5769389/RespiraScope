from collections import deque
from typing import Optional

import numpy as np
from scipy import signal


class PeakValleyDetector:
    def __init__(
        self,
        min_peak_height: float | None = None,
        min_peak_distance: int = 20,
        min_valley_distance: int = 20,
        prominence: float = 5.0,
        buffer_size: int = 500,
        sampling_rate: int = 50,
        low_bpm: float = 6.0,
        high_bpm: float = 40.0,
        peak_threshold_ratio: float = 0.25,
        auto_peak_detection: bool = True,
        confirm_realtime_events: bool = False,
        confirmation_delay_points: int = 12,
        data_gap_reset_points: int = 25,
        gap_warmup_points: int = 75,
    ):
        self.min_peak_height = min_peak_height
        self.min_peak_distance = min_peak_distance
        self.min_valley_distance = min_valley_distance
        self.prominence = prominence
        self.buffer_size = buffer_size
        self.sampling_rate = sampling_rate
        self.low_bpm = low_bpm
        self.high_bpm = high_bpm
        self.peak_threshold_ratio = peak_threshold_ratio
        self.auto_peak_detection = auto_peak_detection
        self.confirm_realtime_events = confirm_realtime_events
        self.confirmation_delay_points = confirmation_delay_points
        self.data_gap_reset_points = data_gap_reset_points
        self.gap_warmup_points = gap_warmup_points

        self.data_buffer = deque(maxlen=buffer_size)
        self.sequence_buffer = deque(maxlen=buffer_size)
        self.detected_peaks = set()
        self.detected_valleys = set()
        self.last_event_type = None
        self.last_event_sequence = None
        self.peak_queue = deque(maxlen=1000)
        self.valley_queue = deque(maxlen=1000)
        self.output_handlers = []
        self.pending_events = {}

    def add_output_handler(self, handler):
        self.output_handlers.append(handler)

    def update_from_filter_config(self, config):
        self.sampling_rate = config.sampling_rate
        self.low_bpm = config.low_bpm
        self.high_bpm = config.high_bpm
        self.min_peak_distance = config.min_peak_distance
        self.min_valley_distance = config.min_peak_distance
        self.peak_threshold_ratio = config.peak_threshold_ratio
        self.prominence = config.prominence
        self.auto_peak_detection = config.auto_peak_detection
        self.confirm_realtime_events = config.confirm_realtime_events
        self.confirmation_delay_points = config.confirmation_delay_points
        self.data_gap_reset_points = config.data_gap_reset_points
        self.gap_warmup_points = config.gap_warmup_points
        self.clear_history()

        for handler in self.output_handlers:
            if hasattr(handler, "update_sampling_rate"):
                handler.update_sampling_rate(config.sampling_rate)

    def handle_filtered_data(self, sequences: list[int], values: list[float]):
        for seq, val in zip(sequences, values):
            sequence = int(seq)
            if self._has_sequence_gap(sequence):
                self._reset_realtime_context()
            self.data_buffer.append(val)
            self.sequence_buffer.append(sequence)

        if len(self.data_buffer) >= max(100, int(self.gap_warmup_points)):
            self._detect_peaks_valleys()

    def detect_peak_valley_batch(self, data_array, sequence_array):
        if data_array is None or sequence_array is None:
            return [], []

        data_array = np.asarray(data_array)
        sequence_array = np.asarray(sequence_array)
        peak_ans = []
        valley_ans = []

        for data_segment, sequence_segment in self._continuous_segments(data_array, sequence_array):
            events = self._collapse_alternating_events(self._candidate_events(data_segment, sequence_segment))
            for event in events:
                item = {
                    "sequence": int(event["sequence"]),
                    "value": float(event["value"]),
                }
                if event["type"] == "peak":
                    peak_ans.append(item)
                else:
                    valley_ans.append(item)

        return peak_ans, valley_ans

    def _has_sequence_gap(self, sequence: int) -> bool:
        if not self.sequence_buffer:
            return False
        previous = int(self.sequence_buffer[-1])
        return sequence - previous > max(1, int(self.data_gap_reset_points))

    def _continuous_segments(self, data_array: np.ndarray, sequence_array: np.ndarray):
        if len(data_array) == 0:
            return []

        segments = []
        start = 0
        gap_threshold = max(1, int(self.data_gap_reset_points))
        for index in range(1, len(sequence_array)):
            if int(sequence_array[index]) - int(sequence_array[index - 1]) > gap_threshold:
                if index - start > 0:
                    segments.append((data_array[start:index], sequence_array[start:index]))
                start = index
        if len(sequence_array) - start > 0:
            segments.append((data_array[start:], sequence_array[start:]))
        return segments

    def _reset_realtime_context(self):
        self.detected_peaks.clear()
        self.detected_valleys.clear()
        self.last_event_type = None
        self.last_event_sequence = None
        self.data_buffer.clear()
        self.sequence_buffer.clear()
        self.pending_events.clear()

    def calculate_metrics(self, peaks: list[dict]) -> dict:
        return BreathRateCalculator(self.sampling_rate).metrics_from_peaks(peaks)

    def _detect_peaks_valleys(self):
        if len(self.data_buffer) < 50:
            return

        data_array = np.array(self.data_buffer)
        sequence_array = np.array(self.sequence_buffer)
        events = self._candidate_events(data_array, sequence_array)
        if self.confirm_realtime_events:
            self._queue_and_flush_confirmed_events(events, int(sequence_array[-1]))
            return

        for event in events:
            self._accept_realtime_event(event)

    def _queue_and_flush_confirmed_events(self, events: list[dict], latest_sequence: int):
        current_keys = set()
        for event in events:
            if self._was_detected(event):
                continue
            key = (event["type"], event["sequence"])
            current_keys.add(key)
            self.pending_events[key] = event

        for key in list(self.pending_events):
            if key not in current_keys:
                del self.pending_events[key]

        confirmation_cutoff = latest_sequence - max(0, int(self.confirmation_delay_points))
        due_events = [
            event
            for event in self.pending_events.values()
            if event["sequence"] <= confirmation_cutoff
        ]
        for event in sorted(due_events, key=lambda item: item["sequence"]):
            key = (event["type"], event["sequence"])
            self.pending_events.pop(key, None)
            self._accept_realtime_event(event)

    def _candidate_events(self, data_array: np.ndarray, sequence_array: np.ndarray) -> list[dict]:
        events = []
        for idx in self._find_peaks(data_array):
            events.append({
                "type": "peak",
                "sequence": int(sequence_array[idx]),
                "value": float(data_array[idx]),
            })

        for idx in self._find_valleys(data_array):
            events.append({
                "type": "valley",
                "sequence": int(sequence_array[idx]),
                "value": float(data_array[idx]),
            })

        return sorted(events, key=lambda item: item["sequence"])

    def _collapse_alternating_events(self, events: list[dict]) -> list[dict]:
        accepted = []
        for event in events:
            if not accepted:
                accepted.append(event)
                continue

            last = accepted[-1]
            if event["type"] == last["type"]:
                if self._is_stronger_same_type(event, last):
                    accepted[-1] = event
                continue

            if event["sequence"] - last["sequence"] < self._min_turn_distance():
                continue

            accepted.append(event)

        return accepted

    def _accept_realtime_event(self, event: dict):
        if self._was_detected(event):
            return

        if self.last_event_sequence is not None:
            if event["sequence"] <= self.last_event_sequence:
                self._remember_event(event)
                return
            if event["sequence"] - self.last_event_sequence < self._min_turn_distance():
                self._remember_event(event)
                return

        if self.last_event_type == event["type"]:
            self._remember_event(event)
            return

        self._remember_event(event)
        self.last_event_type = event["type"]
        self.last_event_sequence = event["sequence"]

        point_data = {
            "sequence": event["sequence"],
            "value": event["value"],
        }
        if event["type"] == "peak":
            self._send_peak_data(point_data)
        else:
            self._send_valley_data(point_data)

    def _was_detected(self, event: dict) -> bool:
        if event["type"] == "peak":
            return event["sequence"] in self.detected_peaks
        return event["sequence"] in self.detected_valleys

    def _remember_event(self, event: dict):
        if event["type"] == "peak":
            self.detected_peaks.add(event["sequence"])
        else:
            self.detected_valleys.add(event["sequence"])

    def _is_stronger_same_type(self, event: dict, last: dict) -> bool:
        if event["type"] == "peak":
            return event["value"] > last["value"]
        return event["value"] < last["value"]

    def _min_turn_distance(self) -> int:
        return max(1, int(self._distance_from_bpm(self.min_peak_distance) * 0.45))

    def _find_peaks(self, data: np.ndarray) -> np.ndarray:
        peaks, _ = signal.find_peaks(
            data,
            height=self.min_peak_height,
            distance=self._distance_from_bpm(self.min_peak_distance),
            prominence=self._prominence(data),
        )
        return peaks

    def _find_valleys(self, data: np.ndarray) -> np.ndarray:
        valleys, _ = signal.find_peaks(
            -data,
            distance=self._distance_from_bpm(self.min_valley_distance),
            prominence=self._prominence(data),
        )
        return valleys

    def _distance_from_bpm(self, fallback: int) -> int:
        if not self.auto_peak_detection or self.high_bpm <= 0:
            return max(1, fallback)
        min_interval_sec = 60.0 / self.high_bpm
        return max(1, int(self.sampling_rate * min_interval_sec * 0.65))

    def _prominence(self, data: np.ndarray) -> float:
        if not self.auto_peak_detection:
            return max(0.01, self.prominence)

        if len(data) < 8:
            return max(0.01, self.prominence)

        signal_span = float(np.percentile(data, 95) - np.percentile(data, 5))
        diff_noise = float(np.median(np.abs(np.diff(data)))) if len(data) > 1 else 0.0
        adaptive_prominence = max(
            0.5,
            signal_span * self.peak_threshold_ratio,
            diff_noise * 3,
        )
        return adaptive_prominence

    def _send_peak_data(self, peak_data: dict):
        self.peak_queue.append(peak_data)
        for handler in self.output_handlers:
            if hasattr(handler, "handle_peak"):
                handler.handle_peak(peak_data)

    def _send_valley_data(self, valley_data: dict):
        self.valley_queue.append(valley_data)
        for handler in self.output_handlers:
            if hasattr(handler, "handle_valley"):
                handler.handle_valley(valley_data)

    def get_recent_peaks_valleys(self, count: int = 10):
        return list(self.peak_queue)[-count:], list(self.valley_queue)[-count:]

    def update_parameters(
        self,
        min_peak_height: float | None = None,
        min_peak_distance: int | None = None,
        min_valley_distance: int | None = None,
        prominence: float | None = None,
    ):
        if min_peak_height is not None:
            self.min_peak_height = min_peak_height
        if min_peak_distance is not None:
            self.min_peak_distance = min_peak_distance
        if min_valley_distance is not None:
            self.min_valley_distance = min_valley_distance
        if prominence is not None:
            self.prominence = prominence

    def clear_history(self):
        self._reset_realtime_context()


class PeakValleyHandler:
    def __init__(self, queue_manager):
        self.queue_manager = queue_manager
        self.breath_rate_calculator = BreathRateCalculator()

    def update_sampling_rate(self, sampling_rate: int):
        self.breath_rate_calculator.sampling_rate = sampling_rate

    def handle_peak(self, peak_data: dict):
        self.queue_manager.handle_peak(peak_data)
        self.breath_rate_calculator.add_peak(peak_data)
        metrics = self.breath_rate_calculator.get_metrics()
        if metrics["bpm"] is not None:
            self.queue_manager.handle_metrics(metrics)

    def handle_valley(self, valley_data: dict):
        self.queue_manager.handle_valley(valley_data)
        self.breath_rate_calculator.add_valley(valley_data)


class BreathRateCalculator:
    def __init__(self, sampling_rate: int = 50, window_size: int = 10):
        self.sampling_rate = sampling_rate
        self.window_size = window_size
        self.peak_sequences = deque(maxlen=window_size)
        self.valley_sequences = deque(maxlen=window_size)

    def add_peak(self, peak_data: dict):
        self.peak_sequences.append(int(peak_data["sequence"]))

    def add_valley(self, valley_data: dict):
        self.valley_sequences.append(int(valley_data["sequence"]))

    def get_breath_rate(self) -> Optional[float]:
        metrics = self.get_metrics()
        return metrics["bpm"]

    def get_metrics(self) -> dict:
        return self.metrics_from_sequences(list(self.peak_sequences))

    def metrics_from_peaks(self, peaks: list[dict]) -> dict:
        return self.metrics_from_sequences([int(item["sequence"]) for item in peaks])

    def metrics_from_sequences(self, peak_sequences: list[int]) -> dict:
        if len(peak_sequences) < 2:
            return {
                "bpm": None,
                "quality": "insufficient",
                "breath_count": len(peak_sequences),
                "interval_cv": None,
            }

        intervals = np.diff(sorted(peak_sequences)) / self.sampling_rate
        intervals = intervals[intervals > 0]
        if len(intervals) == 0:
            return {
                "bpm": None,
                "quality": "insufficient",
                "breath_count": len(peak_sequences),
                "interval_cv": None,
            }

        avg_interval = float(np.mean(intervals))
        bpm = 60.0 / avg_interval
        interval_cv = float(np.std(intervals) / avg_interval) if avg_interval else None

        if interval_cv is None:
            quality = "insufficient"
        elif interval_cv < 0.15:
            quality = "stable"
        elif interval_cv < 0.35:
            quality = "variable"
        else:
            quality = "irregular"

        return {
            "bpm": round(bpm, 2),
            "quality": quality,
            "breath_count": len(peak_sequences),
            "interval_cv": round(interval_cv, 3) if interval_cv is not None else None,
        }
