"""Record binning in sequence coordinates, matching the offline UI contract."""
import math
from ct_breath.binning.segments import binning_segments


def build_respiratory_bins(filtered, peaks, valleys, options, *, gap=25, start=None, end=None, invalid_intervals=(), sampling_rate=50):
    count = options.get('totalBins', 10) // 2
    data = [(p['sequence'], p['value']) for p in filtered]
    events = sorted(
        [(p['sequence'], 'peak') for p in peaks] +
        [(p['sequence'], 'valley') for p in valleys]
    )
    bins = []
    fixed = options['basis'] == 'amplitude' and options['amplitudeMode'] == 'fixed'
    if fixed and (not isinstance(options.get('lower'), (int,float)) or
                  not isinstance(options.get('upper'), (int,float)) or
                  not math.isfinite(options['lower']) or not math.isfinite(options['upper']) or
                  options['lower'] >= options['upper']):
        return []
    for segment, rising in binning_segments(data, events, invalid_intervals, gap, fixed, sampling_rate):
        left, right = segment[0][0], segment[-1][0]
        direction = 'inhale' if rising == options['inhaleRising'] else 'exhale'
        if options['basis'] == 'time':
            bins.extend({'start': left + (right-left)*i/count, 'end': left + (right-left)*(i+1)/count,
                         'direction': direction, 'bin': i+1} for i in range(count))
            continue
        lo = options['lower'] if fixed else min(segment[0][1], segment[-1][1])
        hi = options['upper'] if fixed else max(segment[0][1], segment[-1][1])
        levels = [lo + (hi-lo)*i/count for i in range(count+1)]
        previous = None
        for (x0, y0), (x1, y1) in zip(segment, segment[1:]):
            fractions = [0, 1]
            if y1 != y0:
                fractions.extend(f for level in levels if 0 < (f := (level-y0)/(y1-y0)) < 1)
            fractions.sort()
            for f0, f1 in zip(fractions, fractions[1:]):
                value = y0 + (y1-y0)*(f0+f1)/2
                if value < lo or value > hi:
                    previous = None
                    continue
                band = min(count-1, math.floor((value-lo)/(hi-lo)*count))
                number = band+1 if rising else count-band
                a, b = x0+(x1-x0)*f0, x0+(x1-x0)*f1
                if b <= a:
                    continue
                if previous and previous['bin'] == number and abs(previous['end']-a) < 1e-7:
                    previous['end'] = b
                else:
                    previous = {'start': a, 'end': b, 'direction': direction, 'bin': number}
                    bins.append(previous)
    # Padding helps locate extrema but is not part of the reconstruction interval.
    clipped = []
    for item in bins:
        a = max(item['start'], start) if start is not None else item['start']
        b = min(item['end'], end) if end is not None else item['end']
        if b > a:
            clipped.append({**item, 'start': a, 'end': b})
    return clipped


def annotate_extrema(points, options):
    fixed = options['basis'] == 'amplitude' and options['amplitudeMode'] == 'fixed'
    for point in points:
        location = 'not_applicable'
        if fixed:
            location = ('below' if point['value'] < options['lower'] else
                        'above' if point['value'] > options['upper'] else 'inside')
        point['amplitudeRange'] = location
        point['outOfRange'] = location != 'inside' if fixed else None


def build_binning_metadata(options, intervals):
    count = options.get('totalBins', 10) // 2
    fixed = options['basis'] == 'amplitude' and options['amplitudeMode'] == 'fixed'
    edges = [options['lower'] + (options['upper']-options['lower'])*i/count for i in range(count+1)] if fixed else None
    groups = []
    for direction in ['inhale', 'exhale']:
        rising = (direction == 'inhale') == options['inhaleRising']
        for number in range(1, count+1):
            band = (number if rising else count+1-number) if fixed else None
            groups.append({
                'direction': direction, 'bin': number, 'amplitudeBand': band,
                'amplitudeLower': edges[band-1] if fixed else None,
                'amplitudeUpper': edges[band] if fixed else None,
                'intervals': [{'start': b['start'], 'end': b['end']} for b in intervals
                              if b['direction'] == direction and b['bin'] == number],
            })
    return {
        'version': 1, 'basis': options['basis'],
        'amplitudeMode': options['amplitudeMode'] if options['basis'] == 'amplitude' else None,
        'binsPerDirection': count, 'totalBins': count*2, 'inhaleRising': options['inhaleRising'],
        'amplitudeBounds': {'lower': options['lower'], 'upper': options['upper']} if fixed else None,
        'amplitudeEdges': edges, 'intervalConvention': '[start,end)', 'groups': groups,
    }
