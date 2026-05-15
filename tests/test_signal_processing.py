import asyncio

import numpy as np

from ct_breath.breath_process.filter_strategies import OfflineFilterStrategy, RealtimeFilterStrategy
from ct_breath.breath_process.signal_processor import SignalProcessor
from ct_breath.http.schemas import FilterConfig, normalize_filter_config


def breathing_wave(seconds=60, bpm=12, amplitude=100, baseline=500, sampling_rate=50):
    t = np.arange(0, seconds, 1 / sampling_rate)
    wave = baseline + amplitude * np.sin(2 * np.pi * (bpm / 60) * t)
    return wave


def raw_points(values):
    return [[index, float(value)] for index, value in enumerate(values)]


def filter_config(**overrides):
    return normalize_filter_config(FilterConfig(
        low_bpm=5,
        high_bpm=35,
        gaussian_sigma=1.2,
        peak_threshold_ratio=0.25,
        prominence=0.5,
        **overrides,
    ))


def test_offline_filter_handles_stable_breathing():
    values = breathing_wave(seconds=30, bpm=12)
    processor = SignalProcessor(offline_strategy=OfflineFilterStrategy())
    processor.update_filter_config(filter_config())

    filtered, sequences, payload = asyncio.run(processor.filter_data(raw_points(values)))

    assert filtered is not None
    assert len(filtered) == len(values)
    assert len(sequences) == len(values)
    assert len(payload) == len(values)
    assert np.std(filtered) > 10


def test_realtime_filter_returns_recent_window_only_after_startup():
    values = breathing_wave(seconds=10, bpm=15)
    processor = SignalProcessor(step_size=5, realtime_strategy=RealtimeFilterStrategy())
    processor.update_filter_config(filter_config())

    filtered, sequences = asyncio.run(processor.apply_realtime_filter(values.tolist(), list(range(len(values)))))

    assert filtered is not None
    assert len(filtered) == len(values)
    assert sequences[-1] == len(values) - 1


def test_filter_returns_none_for_sudden_short_stream():
    values = breathing_wave(seconds=2, bpm=12)
    processor = SignalProcessor()
    processor.update_filter_config(filter_config())

    filtered, sequences, payload = asyncio.run(processor.filter_data(raw_points(values)))

    assert filtered is None
    assert sequences is None
    assert payload is None
