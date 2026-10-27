from collections import deque
from statistics import median


QUALITY_GOOD = "good"
QUALITY_LOW_AMPLITUDE = "low_amplitude"
QUALITY_ARTIFACT = "artifact"
QUALITY_NOISY = "noisy"
QUALITY_GAP = "gap"


class SignalQualityAnalyzer:
    def __init__(
        self,
        sampling_rate: int = 50,
        window_seconds: int = 4,
        low_amplitude_threshold: float = 8.0,
        artifact_delta_threshold: float = 120.0,
        noisy_diff_threshold: float = 20.0,
        event_cooldown_points: int | None = None,
    ):
        self.sampling_rate = sampling_rate
        self.window_size = max(8, int(sampling_rate * window_seconds))
        self.low_amplitude_threshold = low_amplitude_threshold
        self.artifact_delta_threshold = artifact_delta_threshold
        self.noisy_diff_threshold = noisy_diff_threshold
        self.event_cooldown_points = event_cooldown_points or sampling_rate * 2
        self.values = deque(maxlen=self.window_size)
        self.sequences = deque(maxlen=self.window_size)
        self.output_handlers = []
        self.last_event_sequence_by_type: dict[str, int] = {}
        self.event_counts = {
            QUALITY_LOW_AMPLITUDE: 0,
            QUALITY_ARTIFACT: 0,
            QUALITY_NOISY: 0,
            QUALITY_GAP: 0,
        }
        self.current_quality = QUALITY_GOOD
        self.last_event: dict | None = None

    def add_output_handler(self, handler):
        if handler not in self.output_handlers:
            self.output_handlers.append(handler)

    def update_sampling_rate(self, sampling_rate: int):
        self.sampling_rate = max(1, int(sampling_rate))
        self.window_size = max(8, self.sampling_rate * 4)
        self.values = deque(self.values, maxlen=self.window_size)
        self.sequences = deque(self.sequences, maxlen=self.window_size)
        self.event_cooldown_points = self.sampling_rate * 2

    def clear_history(self):
        self.values.clear()
        self.sequences.clear()
        self.last_event_sequence_by_type.clear()
        self.current_quality = QUALITY_GOOD
        self.last_event = None

    def handle_data(self, sequence_number, sensor_val):
        sequence = int(sequence_number)
        value = float(sensor_val)

        if self.sequences:
            previous_sequence = int(self.sequences[-1])
            if sequence - previous_sequence > self.sampling_rate:
                self._emit_event(QUALITY_GAP, sequence, value, {
                    "gap_points": sequence - previous_sequence,
                })

        previous_value = self.values[-1] if self.values else None
        if previous_value is not None:
            delta = abs(value - previous_value)
            baseline_delta = abs(value - median(self.values)) if self.values else 0.0
            if delta >= self._artifact_threshold() or baseline_delta >= self._baseline_artifact_threshold():
                self.values.append(value)
                self.sequences.append(sequence)
                self._emit_event(QUALITY_ARTIFACT, sequence, value, {
                    "delta": round(delta, 3),
                    "baseline_delta": round(baseline_delta, 3),
                    "kind": "sudden_change",
                })
                return

        self.values.append(value)
        self.sequences.append(sequence)

        if len(self.values) < max(12, self.sampling_rate):
            self.current_quality = QUALITY_GOOD
            return

        span = max(self.values) - min(self.values)
        if span <= self.low_amplitude_threshold:
            self._emit_event(QUALITY_LOW_AMPLITUDE, sequence, value, {
                "span": round(span, 3),
            })
            return

        diffs = [abs(b - a) for a, b in zip(self.values, list(self.values)[1:])]
        median_diff = median(diffs) if diffs else 0.0
        if median_diff >= self._noisy_threshold(span):
            self._emit_event(QUALITY_NOISY, sequence, value, {
                "median_diff": round(median_diff, 3),
                "span": round(span, 3),
            })
            return

        self.current_quality = QUALITY_GOOD

    def status(self) -> dict:
        return {
            "current_quality": self.current_quality,
            "last_event": self.last_event,
            "event_counts": dict(self.event_counts),
            "window_points": len(self.values),
        }

    def _artifact_threshold(self) -> float:
        if len(self.values) < 8:
            return self.artifact_delta_threshold
        span = max(self.values) - min(self.values)
        return max(self.artifact_delta_threshold, span * 2.5)

    def _baseline_artifact_threshold(self) -> float:
        if len(self.values) < 8:
            return self.artifact_delta_threshold
        span = max(self.values) - min(self.values)
        return max(self.artifact_delta_threshold, span * 1.2)

    def _noisy_threshold(self, span: float) -> float:
        return max(self.noisy_diff_threshold, span * 0.25)

    def _emit_event(self, event_type: str, sequence: int, value: float, details: dict):
        if not self._should_emit(event_type, sequence):
            self.current_quality = event_type
            return

        event = {
            "sequence": sequence,
            "value": value,
            "quality": event_type,
            "details": details,
        }
        self.current_quality = event_type
        self.last_event = event
        self.last_event_sequence_by_type[event_type] = sequence
        self.event_counts[event_type] = self.event_counts.get(event_type, 0) + 1

        for handler in self.output_handlers:
            if hasattr(handler, "handle_signal_quality"):
                handler.handle_signal_quality(event)

    def _should_emit(self, event_type: str, sequence: int) -> bool:
        last_sequence = self.last_event_sequence_by_type.get(event_type)
        if last_sequence is None:
            return True
        return sequence - last_sequence >= self.event_cooldown_points


def analyze_signal_quality_batch(points: list[list[int | float]], sampling_rate: int = 50) -> list[dict]:
    analyzer = SignalQualityAnalyzer(sampling_rate=sampling_rate)
    events = []

    class CaptureHandler:
        def handle_signal_quality(self, event):
            events.append(event)

    analyzer.add_output_handler(CaptureHandler())
    for point in points:
        if len(point) < 2:
            continue
        analyzer.handle_data(point[0], point[1])
    return events
