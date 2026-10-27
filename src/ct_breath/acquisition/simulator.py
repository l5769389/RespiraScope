import math
import random
import threading
from dataclasses import asdict, dataclass, replace
from typing import Any


@dataclass(frozen=True)
class MockBreathConfig:
    scenario: str = "normal"
    bpm: float = 18.0
    amplitude: float = 110.0
    baseline: float = 180.0
    noise: float = 3.0
    drift: float = 4.0
    irregularity: float = 0.03
    apnea_interval_sec: float = 0.0
    apnea_duration_sec: float = 0.0
    artifact_chance: float = 0.0
    artifact_amplitude: float = 0.0
    sample_interval_ms: int = 20


SCENARIO_PRESETS: dict[str, MockBreathConfig] = {
    "normal": MockBreathConfig(),
    "tachypnea": MockBreathConfig(
        scenario="tachypnea",
        bpm=32.0,
        amplitude=75.0,
        noise=4.0,
        irregularity=0.08,
    ),
    "bradypnea": MockBreathConfig(
        scenario="bradypnea",
        bpm=8.0,
        amplitude=135.0,
        noise=2.0,
        drift=5.0,
        irregularity=0.04,
    ),
    "shallow": MockBreathConfig(
        scenario="shallow",
        bpm=20.0,
        amplitude=36.0,
        noise=5.0,
        drift=3.0,
        irregularity=0.05,
    ),
    "irregular": MockBreathConfig(
        scenario="irregular",
        bpm=17.0,
        amplitude=105.0,
        noise=5.0,
        drift=6.0,
        irregularity=0.32,
    ),
    "apnea": MockBreathConfig(
        scenario="apnea",
        bpm=16.0,
        amplitude=105.0,
        noise=3.0,
        drift=4.0,
        irregularity=0.08,
        apnea_interval_sec=28.0,
        apnea_duration_sec=8.0,
    ),
    "noisy": MockBreathConfig(
        scenario="noisy",
        bpm=18.0,
        amplitude=95.0,
        noise=18.0,
        drift=8.0,
        irregularity=0.1,
    ),
    "motion_artifact": MockBreathConfig(
        scenario="motion_artifact",
        bpm=18.0,
        amplitude=105.0,
        noise=7.0,
        drift=12.0,
        irregularity=0.08,
        artifact_chance=0.012,
        artifact_amplitude=170.0,
    ),
    "deep": MockBreathConfig(
        scenario="deep",
        bpm=10.0,
        amplitude=170.0,
        noise=2.0,
        drift=4.0,
        irregularity=0.03,
    ),
    "rapid_shallow": MockBreathConfig(
        scenario="rapid_shallow",
        bpm=36.0,
        amplitude=32.0,
        noise=5.0,
        drift=3.0,
        irregularity=0.12,
    ),
    "baseline_drift": MockBreathConfig(
        scenario="baseline_drift",
        bpm=18.0,
        amplitude=92.0,
        noise=4.0,
        drift=28.0,
        irregularity=0.05,
    ),
    "periodic_weakening": MockBreathConfig(
        scenario="periodic_weakening",
        bpm=14.0,
        amplitude=115.0,
        noise=3.0,
        drift=5.0,
        irregularity=0.1,
        apnea_interval_sec=22.0,
        apnea_duration_sec=5.0,
    ),
    "weak_noisy": MockBreathConfig(
        scenario="weak_noisy",
        bpm=18.0,
        amplitude=28.0,
        noise=12.0,
        drift=8.0,
        irregularity=0.08,
    ),
    "cough_artifact": MockBreathConfig(
        scenario="cough_artifact",
        bpm=20.0,
        amplitude=82.0,
        noise=6.0,
        drift=7.0,
        irregularity=0.1,
        artifact_chance=0.025,
        artifact_amplitude=240.0,
    ),
}


class BreathWaveform:
    def __init__(self, config_provider, seed: int | None = None):
        self.config_provider = config_provider
        self.rng = random.Random(seed)
        self.phase = 0.0
        self.last_elapsed_sec = 0.0
        self.artifact_remaining = 0
        self.artifact_value = 0.0

    def value_at(self, elapsed_sec: float) -> int:
        config = self.config_provider()
        dt = max(0.0, elapsed_sec - self.last_elapsed_sec)
        self.last_elapsed_sec = elapsed_sec

        bpm = self._current_bpm(config, elapsed_sec)
        self.phase += 2 * math.pi * (bpm / 60.0) * dt

        signal_value = self._breath_shape(self.phase)
        apnea_scale = self._apnea_scale(config, elapsed_sec)
        baseline = config.baseline + config.drift * math.sin(2 * math.pi * elapsed_sec / 45.0)
        value = baseline + apnea_scale * config.amplitude * signal_value
        value += self.rng.gauss(0, config.noise)
        value += self._artifact(config)

        return max(0, min(65535, int(round(value))))

    def _current_bpm(self, config: MockBreathConfig, elapsed_sec: float) -> float:
        slow_variation = math.sin(2 * math.pi * elapsed_sec / 17.0)
        fast_variation = math.sin(2 * math.pi * elapsed_sec / 7.0 + 0.7)
        multiplier = 1 + config.irregularity * (0.55 * slow_variation + 0.45 * fast_variation)
        return max(3.0, config.bpm * multiplier)

    def _breath_shape(self, phase: float) -> float:
        return (
            0.82 * math.sin(phase)
            + 0.18 * math.sin(2 * phase - 0.8)
            + 0.06 * math.sin(3 * phase + 0.4)
        )

    def _apnea_scale(self, config: MockBreathConfig, elapsed_sec: float) -> float:
        if config.apnea_interval_sec <= 0 or config.apnea_duration_sec <= 0:
            return 1.0
        position = elapsed_sec % config.apnea_interval_sec
        if position >= config.apnea_duration_sec:
            return 1.0
        edge = min(1.5, config.apnea_duration_sec / 3)
        if position < edge:
            return max(0.08, 1 - position / edge)
        if position > config.apnea_duration_sec - edge:
            return max(0.08, (position - (config.apnea_duration_sec - edge)) / edge)
        return 0.08

    def _artifact(self, config: MockBreathConfig) -> float:
        if self.artifact_remaining <= 0 and self.rng.random() < config.artifact_chance:
            self.artifact_remaining = self.rng.randint(6, 20)
            direction = 1 if self.rng.random() > 0.5 else -1
            self.artifact_value = direction * config.artifact_amplitude

        if self.artifact_remaining <= 0:
            return 0.0

        self.artifact_remaining -= 1
        decay = self.artifact_remaining / 20
        return self.artifact_value * max(0.0, decay)


class MockBreathController:
    def __init__(self):
        self._lock = threading.Lock()
        self._config = SCENARIO_PRESETS["normal"]

    def get_config(self) -> MockBreathConfig:
        with self._lock:
            return self._config

    def set_config(self, values: dict[str, Any]) -> MockBreathConfig:
        scenario = values.get("scenario") or self.get_config().scenario
        base = SCENARIO_PRESETS.get(scenario, SCENARIO_PRESETS["normal"])
        allowed = set(MockBreathConfig.__dataclass_fields__.keys())
        overrides = {key: value for key, value in values.items() if key in allowed and value is not None}
        overrides["scenario"] = scenario if scenario in SCENARIO_PRESETS else base.scenario
        with self._lock:
            self._config = replace(base, **overrides)
            return self._config

    def create_waveform(self, seed: int | None = None) -> BreathWaveform:
        return BreathWaveform(self.get_config, seed=seed)

    def list_scenarios(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "config": asdict(config),
            }
            for name, config in SCENARIO_PRESETS.items()
        ]


mock_breath_controller = MockBreathController()


def config_to_dict(config: MockBreathConfig) -> dict[str, Any]:
    return asdict(config)


def generate_preview(config: MockBreathConfig, seconds: float, sampling_rate: int) -> list[list[float]]:
    fixed_config = config
    waveform = BreathWaveform(lambda: fixed_config, seed=42)
    sample_count = max(1, int(seconds * sampling_rate))
    return [
        [index, waveform.value_at(index / sampling_rate)]
        for index in range(sample_count)
    ]
