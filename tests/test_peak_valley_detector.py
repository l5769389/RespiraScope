import numpy as np

from ct_breath.breath_process.peak_valley_detector import PeakValleyDetector
from ct_breath.http.schemas import FilterConfig


class CaptureHandler:
    def __init__(self):
        self.peaks = []
        self.valleys = []

    def handle_peak(self, peak_data):
        self.peaks.append(peak_data)

    def handle_valley(self, valley_data):
        self.valleys.append(valley_data)


def breathing_wave(seconds=60, bpm=12, amplitude=100, baseline=500, sampling_rate=50):
    t = np.arange(0, seconds, 1 / sampling_rate)
    return baseline + amplitude * np.sin(2 * np.pi * (bpm / 60) * t)


def detector(**overrides):
    params = {
        "sampling_rate": 50,
        "low_bpm": 5,
        "high_bpm": 35,
        "peak_threshold_ratio": 0.2,
        "prominence": 0.5,
        "auto_peak_detection": True,
    }
    params.update(overrides)
    instance = PeakValleyDetector(**params)
    return instance


def combined_events(peaks, valleys):
    return sorted(
        [{"type": "peak", **item} for item in peaks] + [{"type": "valley", **item} for item in valleys],
        key=lambda item: item["sequence"],
    )


def assert_alternating(peaks, valleys):
    events = combined_events(peaks, valleys)
    for previous, current in zip(events, events[1:]):
        assert previous["type"] != current["type"]


def test_detects_stable_breathing_bpm():
    values = breathing_wave(seconds=60, bpm=12)
    sequences = np.arange(len(values))
    d = detector()

    peaks, valleys = d.detect_peak_valley_batch(values, sequences)
    metrics = d.calculate_metrics(peaks)

    assert 9 <= len(peaks) <= 13
    assert 9 <= len(valleys) <= 13
    assert 11 <= metrics["bpm"] <= 13
    assert metrics["quality"] == "stable"
    assert_alternating(peaks, valleys)


def test_detects_shallow_breathing():
    values = breathing_wave(seconds=60, bpm=14, amplitude=18)
    sequences = np.arange(len(values))
    d = detector(peak_threshold_ratio=0.15, prominence=0.2)

    peaks, valleys = d.detect_peak_valley_batch(values, sequences)

    assert len(peaks) >= 8
    assert len(valleys) >= 8
    assert_alternating(peaks, valleys)


def test_apnea_segment_reduces_count_and_marks_variability():
    values = breathing_wave(seconds=60, bpm=12)
    values[20 * 50:35 * 50] = 500
    sequences = np.arange(len(values))
    d = detector()

    peaks, valleys = d.detect_peak_valley_batch(values, sequences)
    metrics = d.calculate_metrics(peaks)

    assert len(peaks) < 11
    assert metrics["quality"] in {"variable", "irregular"}
    assert metrics["interval_cv"] is None or metrics["interval_cv"] >= 0.15
    assert_alternating(peaks, valleys)


def test_motion_artifact_does_not_produce_consecutive_same_type_events():
    values = breathing_wave(seconds=60, bpm=12)
    values[500] += 350
    values[900] -= 350
    values[1450] += 450
    sequences = np.arange(len(values))
    d = detector(peak_threshold_ratio=0.25, prominence=1.0)

    peaks, valleys = d.detect_peak_valley_batch(values, sequences)

    assert len(peaks) > 0
    assert len(valleys) > 0
    assert_alternating(peaks, valleys)


def test_realtime_confirmation_delays_peak_output():
    values = breathing_wave(seconds=12, bpm=12)
    sequences = list(range(len(values)))
    config = FilterConfig(
        low_bpm=5,
        high_bpm=35,
        confirm_realtime_events=True,
        confirmation_delay_points=80,
    )
    d = detector()
    d.update_from_filter_config(config)
    capture = CaptureHandler()
    d.add_output_handler(capture)

    d.handle_filtered_data(sequences[:100], values[:100].tolist())
    early_count = len(capture.peaks) + len(capture.valleys)
    d.handle_filtered_data(sequences[100:180], values[100:180].tolist())
    later_count = len(capture.peaks) + len(capture.valleys)

    assert early_count == 0
    assert later_count > 0


def test_sudden_stream_stop_does_not_crash_realtime_detector():
    values = breathing_wave(seconds=8, bpm=12)
    d = detector()
    capture = CaptureHandler()
    d.add_output_handler(capture)

    d.handle_filtered_data(list(range(120)), values[:120].tolist())
    d.handle_filtered_data(list(range(120, 230)), values[120:230].tolist())

    assert len(capture.peaks) + len(capture.valleys) >= 0


def test_realtime_detector_keeps_bounded_recent_event_history():
    d = detector()
    capture = CaptureHandler()
    d.add_output_handler(capture)

    for sequence in range(1200):
        d._send_peak_data({"sequence": sequence * 2, "value": 550.0})
        d._send_valley_data({"sequence": sequence * 2 + 1, "value": 450.0})

    peaks, valleys = d.get_recent_peaks_valleys(5)

    assert len(capture.peaks) == 1200
    assert len(capture.valleys) == 1200
    assert len(d.peak_queue) == 1000
    assert len(d.valley_queue) == 1000
    assert [item["sequence"] for item in peaks] == [2390, 2392, 2394, 2396, 2398]
    assert [item["sequence"] for item in valleys] == [2391, 2393, 2395, 2397, 2399]


def test_sequence_gap_resets_realtime_detector_and_waits_for_warmup():
    first_values = breathing_wave(seconds=8, bpm=12)
    second_values = breathing_wave(seconds=2, bpm=12)
    d = detector(
        confirm_realtime_events=True,
        confirmation_delay_points=10,
        data_gap_reset_points=20,
        gap_warmup_points=120,
    )
    capture = CaptureHandler()
    d.add_output_handler(capture)

    d.handle_filtered_data(list(range(len(first_values))), first_values.tolist())
    event_count_before_gap = len(capture.peaks) + len(capture.valleys)
    d.handle_filtered_data(list(range(1000, 1060)), second_values[:60].tolist())
    event_count_after_gap = len(capture.peaks) + len(capture.valleys)

    assert event_count_after_gap == event_count_before_gap
    assert len(d.data_buffer) == 60
