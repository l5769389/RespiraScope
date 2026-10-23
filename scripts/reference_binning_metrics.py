"""Independent clean-waveform reference labels for the simulation report.

The reference never uses production extrema, quality flags, or binning code.
Extrema are sampled local maxima/minima of the known noise/artifact-free signal.
Time labels divide each reference half-breath in five equal time intervals.
Amplitude labels use the clean sample value and the SAME fixed bounds as the app.
"""
import numpy as np
from scipy.signal import find_peaks


def compare_base_span(clean, filtered, valid):
    """Signed robust amplitude-span change on identical quality-valid timestamps."""
    clean = np.asarray(clean, dtype=float)
    filtered = np.asarray(filtered, dtype=float)
    valid = np.asarray(valid, dtype=bool)
    if clean.shape != filtered.shape or clean.shape != valid.shape or clean.ndim != 1:
        raise ValueError('Signals and mask must be one-dimensional arrays of equal length')
    selected = valid & np.isfinite(clean) & np.isfinite(filtered)
    count = int(selected.sum())
    clean_span = float(np.ptp(np.percentile(clean[selected], [5, 95]))) if count else None
    filtered_span = float(np.ptp(np.percentile(filtered[selected], [5, 95]))) if count else None
    change = 100 * (filtered_span / clean_span - 1) if clean_span and clean_span > 0 else None
    return {'scored_points': count, 'clean_span': clean_span, 'filtered_span': filtered_span,
            'change_percent': change}


def summarize_base_span(runs):
    values = [r['change_percent'] for r in runs if r['change_percent'] is not None]
    return {'change_percent': float(np.mean(values)) if values else None,
            'scored_runs': len(values), 'total_runs': len(runs),
            'scored_points': sum(r['scored_points'] for r in runs if r['change_percent'] is not None)}


def reference_labels(clean, bounds, bins_per_half=5):
    clean = np.asarray(clean, dtype=float)
    peak = find_peaks(clean)[0]
    valley = find_peaks(-clean)[0]
    events = sorted([(int(x), False) for x in peak] + [(int(x), True) for x in valley])
    time = np.full(len(clean), -1, dtype=int)
    fixed = np.full(len(clean), -1, dtype=int)
    lo, hi = bounds
    if not hi > lo:
        raise ValueError('Reference bounds must have positive width')
    for (a, rising), (b, next_rising) in zip(events, events[1:]):
        if rising == next_rising or b <= a:
            continue
        x = np.arange(a, b)
        base = 0 if rising else bins_per_half
        time[x] = base + np.minimum(bins_per_half-1, ((x-a)*bins_per_half)//(b-a))
        in_range = (clean[x] >= lo) & (clean[x] <= hi)
        selected = x[in_range]
        band = np.minimum(bins_per_half-1, np.floor((clean[selected]-lo)/(hi-lo)*bins_per_half).astype(int))
        fixed[selected] = band if rising else base+bins_per_half-1-band
    return {'time': time, 'fixed': fixed}


def compare_reference(actual, reference, valid):
    """Score identical retained timestamps; an amplitude reference outside bounds is a mismatch.

    Missing reference half-breaths are excluded for BOTH modes. Points excluded
    by either actual mode are not accuracy successes and remain outside the denominator.
    """
    valid = np.asarray(valid, dtype=bool)
    actual = {k: np.asarray(actual[k]) for k in ['time', 'fixed']}
    scored = valid & (actual['time'] >= 0) & (actual['fixed'] >= 0) & (reference['time'] >= 0)
    count = int(scored.sum())
    return {'scored_points': count, 'record_points': len(valid),
            'scored_percent': float(scored.mean()*100),
            'modes': {mode: {'mismatch_points': int(np.sum(actual[mode][scored] != reference[mode][scored])),
                             'mismatch_percent': float(np.mean(actual[mode][scored] != reference[mode][scored])*100) if count else None}
                      for mode in ['time', 'fixed']}}


def summarize_reference(runs):
    count = sum(r['scored_points'] for r in runs)
    total = sum(r['record_points'] for r in runs)
    return {'scored_points': count, 'record_points': total,
            'scored_percent': 100*count/total if total else None,
            'scored_runs': sum(r['scored_points'] > 0 for r in runs), 'total_runs': len(runs),
            'modes': {mode: {'mismatch_points': sum(r['modes'][mode]['mismatch_points'] for r in runs),
                             'mismatch_percent': 100*sum(r['modes'][mode]['mismatch_points'] for r in runs)/count if count else None}
                      for mode in ['time', 'fixed']}}
