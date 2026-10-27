"""Real acquisition context required by the offline filter (per side)."""
import numpy as np


def settling_points(sos):
    """5% slowest-pole envelope; not a bound on waveform amplitude error."""
    radius = max(abs(p) for section in sos for p in np.roots(section[3:]))
    return max(1, int(np.ceil(np.log(.05)/np.log(radius))))


def recording_padding(app_config):
    """Fixed startup configuration shared by acquisition and offline filtering."""
    return max(0, int(app_config.record_pre_points)), max(0, int(app_config.record_post_points))


def select_filter_context(raw_points, app_config, start=None, end=None):
    if start is None or end is None:
        return raw_points
    pre, post = recording_padding(app_config)
    return [p for p in raw_points if start-pre <= p[0] <= end+post]
