"""Real acquisition context required by the offline filter (per side)."""
import numpy as np


def settling_points(sos):
    """5% slowest-pole envelope; not a bound on waveform amplitude error."""
    radius = max(abs(p) for section in sos for p in np.roots(section[3:]))
    return max(1, int(np.ceil(np.log(.05)/np.log(radius))))


def recording_padding(app_config, filter_config=None):
    """One offline context, independent of the chosen binning basis.

    Explicit shared settings take precedence. Legacy per-mode settings migrate
    using the larger value on each side, so existing captured context is retained.
    """
    return tuple(max(0, int(shared if (shared := getattr(app_config, f'record_{side}_points'))
                            is not None else max(getattr(app_config, f'record_time_{side}_points'),
                                                 getattr(app_config, f'record_amplitude_{side}_points'))))
                 for side in ('pre', 'post'))


def mode_padding(app_config, mode):
    """Compatibility alias for older clients; both modes share the same context."""
    return recording_padding(app_config)


def select_filter_context(raw_points, app_config, mode=None, start=None, end=None):
    if start is None or end is None:
        return raw_points
    pre, post = recording_padding(app_config)
    return [p for p in raw_points if start-pre <= p[0] <= end+post]
