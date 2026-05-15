from abc import ABC, abstractmethod
from collections.abc import Sequence

import numpy as np
from scipy import signal
from scipy.ndimage import gaussian_filter1d

from ct_breath.http.schemas import FilterConfig

FILTER_STARTUP_DELAY = 300


def butterworth_filter(data, cutoff_low, cutoff_high, fs, order, realtime=False):
    nyquist = fs / 2
    low_wn = cutoff_low / nyquist
    high_wn = cutoff_high / nyquist
    sos = signal.butter(order, [low_wn, high_wn], btype="bandpass", output="sos")
    if realtime:
        return signal.sosfilt(sos, data)
    return signal.sosfiltfilt(sos, data)


def gaussian_smooth(data, sigma=1.0):
    return gaussian_filter1d(data, sigma=sigma)


class FilterStrategy(ABC):
    realtime = False

    @abstractmethod
    def filter(
        self,
        data_to_process: Sequence[float],
        sequence_nums: Sequence[int],
        config: FilterConfig,
    ):
        raise NotImplementedError

    def _filter_common(
        self,
        data_to_process: Sequence[float],
        sequence_nums: Sequence[int],
        config: FilterConfig,
    ):
        if len(data_to_process) < FILTER_STARTUP_DELAY:
            return None, None

        process_data = butterworth_filter(
            data_to_process,
            config.lowpass_cutoff,
            config.highpass_cutoff,
            config.sampling_rate,
            config.order,
            realtime=self.realtime,
        )
        if config.restore_baseline:
            process_data = process_data + np.median(data_to_process)
        process_data = gaussian_smooth(process_data, sigma=config.gaussian_sigma)
        return np.round(process_data, 1), sequence_nums


class RealtimeFilterStrategy(FilterStrategy):
    realtime = True

    def filter(
        self,
        data_to_process: Sequence[float],
        sequence_nums: Sequence[int],
        config: FilterConfig,
    ):
        return self._filter_common(data_to_process, sequence_nums, config)


class OfflineFilterStrategy(FilterStrategy):
    realtime = False

    def filter(
        self,
        data_to_process: Sequence[float],
        sequence_nums: Sequence[int],
        config: FilterConfig,
    ):
        return self._filter_common(data_to_process, sequence_nums, config)
