import numpy as np


def breathing_wave(seconds=60, bpm=12, amplitude=100, baseline=500, sampling_rate=50):
    t = np.arange(0, seconds, 1 / sampling_rate)
    return baseline + amplitude * np.sin(2 * np.pi * (bpm / 60) * t)


def raw_points(values):
    return [[index, float(value)] for index, value in enumerate(values)]


def cough_artifact_sample(seconds=20, sampling_rate=50):
    values = breathing_wave(seconds=seconds, bpm=14, sampling_rate=sampling_rate)
    cough_index = 8 * sampling_rate
    values[cough_index] += 420
    values[cough_index + 1] -= 250
    return raw_points(values)


def apnea_sample(seconds=40, sampling_rate=50):
    values = breathing_wave(seconds=seconds, bpm=12, sampling_rate=sampling_rate)
    values[15 * sampling_rate:25 * sampling_rate] = 500
    return raw_points(values)


def low_amplitude_sample(seconds=8, baseline=500, sampling_rate=50):
    values = np.full(seconds * sampling_rate, baseline, dtype=float)
    values += np.sin(np.arange(len(values))) * 1.5
    return raw_points(values)
