"""Conservative offline quality masks in half-open sequence coordinates.

The original samples are never edited. Bounded transients are bridged only in
the working copy; sustained motion separates filter runs. Masked output is
display-only and cannot contribute to extrema, bounds or reconstruction bins.
"""
import numpy as np
from scipy import signal
from scipy.ndimage import median_filter, gaussian_filter1d

from ct_breath.breath_process.filter_context import settling_points


def runs(mask):
    edges = np.diff(np.r_[False, mask, False].astype(int))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))


def valid_runs(sequences, intervals, gap=25):
    seq = np.asarray(sequences)
    valid = np.ones(len(seq), dtype=bool)
    for item in intervals:
        valid &= ~((seq >= item['start']) & (seq < item['end']))
    result = []
    for a, b in runs(valid):
        cuts = np.flatnonzero(np.diff(seq[a:b]) > gap) + a + 1
        edges = [a, *cuts, b]
        result.extend(zip(edges[:-1], edges[1:]))
    return result


def detect_valid_extrema(detector, values, sequences, intervals, gap=25):
    peaks, valleys = [], []
    if values is None or sequences is None:
        return peaks, valleys
    for a, b in valid_runs(sequences, intervals, gap):
        if b-a < 3:
            continue
        p, v = detector.detect_peak_valley_batch(values[a:b], sequences[a:b])
        peaks.extend(p); valleys.extend(v)
    return peaks, valleys


def artifact_masks(values, fs):
    """Require both a robust amplitude departure and an abrupt change.

    Noise scale comes from second differences to avoid labelling ordinary steep
    inhalation as noise. Long abrupt steps are untrusted until a return edge;
    this deliberately does not claim to recognize every kind of body motion.
    """
    x = np.asarray(values, dtype=float)
    n = len(x)
    if n < 5:
        return np.zeros(n, bool), np.zeros(n, bool)
    curvature = np.diff(x, n=2)
    noise = 1.4826*np.median(np.abs(curvature-np.median(curvature)))/np.sqrt(6)
    span = np.percentile(x, 95)-np.percentile(x, 5)
    window = max(5, int(fs) | 1)
    residual = np.abs(x-median_filter(x, size=window, mode='nearest'))
    threshold = max(8*noise, .12*span, 1.)
    delta = np.diff(x)
    jumps = np.flatnonzero(np.abs(delta) > max(8*np.sqrt(2)*noise, .25*span, 1.)) + 1
    candidate = residual > threshold
    spikes = np.zeros(n, bool)
    for a,b in runs(candidate):
        if (b-a <= max(1,int(.12*fs)) and a > 0 and b < n
                and a in jumps and b in jumps and delta[a-1]*delta[b-1] < 0):
            spikes[a:b] = True
    candidate &= ~spikes
    # Include the decaying tail of a transient, but only around a hard seed.
    for a,b in runs(residual > threshold*.25):
        if candidate[a:b].any() and np.any((jumps >= a-1) & (jumps <= b+1)):
            candidate[a:b] = True
        else:
            candidate[a:b] = False
    motion = np.zeros(n, bool)
    for j in jumps:
        if candidate[max(0,j-1):min(n,j+1)].any() or spikes[max(0,j-1):min(n,j+1)].any() or motion[j]:
            continue
        # A persistent displacement has two abrupt opposite edges. If there is
        # no return, the remainder cannot safely share fixed amplitude bounds.
        opposite = [k for k in jumps if j < k <= j+int(20*fs)
                    and delta[k-1]*delta[j-1] < 0
                    and .5 <= abs(delta[k-1]/delta[j-1]) <= 2]
        end = opposite[0] if opposite else n
        motion[max(0,j-1):min(n,end+1)] = True
    for a,b in runs(candidate & ~motion):
        if b-a <= max(1,int(.12*fs)) and a > 0 and b < n:
            spikes[a:b] = True
        else:
            motion[a:b] = True
    return spikes, motion


def filter_offline(values, sequences, config):
    x = np.asarray(values, dtype=float)
    seq = np.asarray(sequences)
    output = np.zeros_like(x)
    # v2 guarantees that motion/too_short samples are filtered references,
    # whereas v1 used raw placeholders. Their quality exclusions are unchanged.
    quality = {'version':2, 'invalidIntervals':[], 'baselines':[]}
    fs = config.sampling_rate
    preserve_baseline = config.offline_filter == 'baseline_lowpass'
    if preserve_baseline:
        sos = signal.butter(config.lowpass_order, config.highpass_cutoff,
                            btype='lowpass', fs=fs, output='sos')
    else:
        sos = signal.butter(config.order, [config.lowpass_cutoff, config.highpass_cutoff],
                            btype='bandpass', fs=fs, output='sos')
    # Conservative pole-envelope settling margin (5%); buffered crop interiors
    # remain usable, while boundaries next to gaps/motion cannot masquerade as data.
    guard = settling_points(sos)

    def exclude(a, b, reason):
        if b > a:
            quality['invalidIntervals'].append({'start':int(seq[a]), 'end':int(seq[b-1])+1, 'reason':reason})

    cuts = np.flatnonzero(np.diff(seq) > config.data_gap_reset_points)+1
    edges = [0, *cuts, len(x)]
    for start, stop in zip(edges[:-1], edges[1:]):
        spikes, motion = artifact_masks(x[start:stop], fs)
        working = x[start:stop].copy()
        reference_mask = motion.copy()
        for a,b in runs(spikes):
            working[a:b] = np.interp(np.arange(a,b), [a-1,b], [working[a-1],working[b]])
            exclude(start+a,start+b,'spike')
            halo = max(1,int(fs*max(.25,1/config.highpass_cutoff)))
            exclude(max(start,start+a-halo), min(stop,start+b+halo),'filter_edge')
        for a,b in runs(motion):
            exclude(start+a,start+b,'motion')
        reference_working = working.copy()
        sustained = motion.copy()
        bridged = np.zeros(len(working), dtype=bool)
        for a,b in runs(motion):
            # A bounded, at-most-one-second excursion can share filter context
            # across its ends. Its interpolant is never accepted for binning.
            # Open-ended displacement and longer motion must still split runs.
            if a > 0 and b < len(working) and b-a <= fs:
                working[a:b] = np.interp(np.arange(a,b), [a-1,b], [working[a-1],working[b]])
                sustained[a:b] = False
                bridged[a:b] = True
                halo = max(1, int(np.ceil(max(.25*fs, 4*config.gaussian_sigma))))
                exclude(max(start,start+a-halo),min(stop,start+b+halo),'filter_edge')
        for a,b in runs(~sustained):
            left,right = start+a,start+b
            if b-a < 300:
                exclude(left,right,'too_short')
                reference_mask[a:b] = True
                continue
            y = gaussian_filter1d(signal.sosfiltfilt(sos, working[a:b]), config.gaussian_sigma)
            if bridged[a:b].any():
                # Local exclusion follows this filter's actual response to the
                # removed excursion, instead of restarting the slow high-pass
                # at every cough. 5% of robust span is a quality heuristic, not
                # a bound on the unknown true waveform inside the excursion.
                uncorrected = gaussian_filter1d(signal.sosfiltfilt(sos, reference_working[a:b]), config.gaussian_sigma)
                tolerance = max(1., .05 * (np.percentile(working[a:b],95)-np.percentile(working[a:b],5)))
                for c,d in runs(np.abs(uncorrected-y) > tolerance):
                    exclude(left+c,left+d,'filter_edge')
            exclude(left,min(right,left+guard),'filter_edge')
            exclude(max(left,right-guard),right,'filter_edge')
            output[left:right] = y
        if reference_mask.any():
            # Diagnostic filtering uses actual samples from this acquisition
            # segment, never crosses missing data and never replaces trusted
            # runs. Short segments use the available padding only.
            default_pad = 3 * (2 * len(sos) + 1 - min(
                (sos[:, 2] == 0).sum(), (sos[:, 5] == 0).sum()))
            reference = gaussian_filter1d(signal.sosfiltfilt(
                sos, reference_working, padlen=min(default_pad, len(working)-1)), config.gaussian_sigma)
            output[start:stop][reference_mask] = reference[reference_mask]
        for cut in cuts:
            if cut == stop:
                quality['invalidIntervals'].append({'start':int(seq[cut-1])+1,'end':int(seq[cut]),'reason':'gap'})

    # One offset per uninterrupted acquisition segment, shared across its cycles.
    # No gain normalization and no per-cycle recentering are performed.
    for start,stop in zip(edges[:-1],edges[1:]):
        if preserve_baseline:
            # DC and slow changes pass directly through the low-pass. Adding a
            # reconstructed offset here would double the baseline.
            quality['baselines'].append({'start':int(seq[start]), 'end':int(seq[stop-1])+1,
                'status':'preserved', 'cycles':0, 'offset':0.})
            continue
        offsets = []
        for a,b in valid_runs(seq[start:stop],quality['invalidIntervals'],config.data_gap_reset_points):
            a += start; b += start
            y = output[a:b]
            if len(y) < 3:
                continue
            span = np.percentile(y,95)-np.percentile(y,5)
            if span < 1:
                continue
            peaks,_ = signal.find_peaks(y, distance=max(1,int(fs*.75)), prominence=max(1,span*.2))
            for p,q in zip(peaks[:-1],peaks[1:]):
                if .75 <= (seq[a+q]-seq[a+p])/fs <= 20:
                    difference = x[a+p:a+q+1]-output[a+p:a+q+1]
                    offsets.append(float(np.trapezoid(difference)/(q-p)))
        estimated = len(offsets) >= 3
        info = {'start':int(seq[start]),'end':int(seq[stop-1])+1,
                'status':'estimated' if estimated else 'insufficient_cycles', 'cycles':len(offsets)}
        offset = float(np.median(offsets)) if estimated else float(np.median(x[start:stop]))
        if config.restore_baseline:
            info['offset'] = offset
        else:
            info['status'] = 'disabled'
            offset = 0.
        output[start:stop] += offset
        quality['baselines'].append(info)
    quality['invalidIntervals'].sort(key=lambda i:(i['start'],i['end'],i['reason']))
    return np.round(output,1), quality
