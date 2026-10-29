"""Complete, non-overlapping binning timeline in original sample coordinates.

Keep the browser implementation in modules/binning-data.js in sync.
"""
from collections import defaultdict
from bisect import bisect_left
import math


def build_binning_timeline(filtered, bins, invalid, options, start, end, fs=50, gap=25):
    fixed = options.get('basis') == 'amplitude' and options.get('amplitudeMode') == 'fixed'
    result = dict(version=3, coordinate='sample_sequence', intervalConvention='[start,end)',
                  range=[start, end], samplingRateHz=fs,
                  method='time' if options.get('basis', 'time') == 'time' else
                  'amplitude-fixed' if fixed else 'amplitude-free',
                  totalBins=options.get('totalBins', 10), inhaleRising=options.get('inhaleRising', True),
                  intervals=[])
    if fixed:
        if (not all(isinstance(options.get(key), (int, float)) and math.isfinite(options[key])
                    for key in ('lower', 'upper')) or options['lower'] >= options['upper']):
            raise ValueError('Fixed amplitude binning requires finite lower < upper bounds')
        result['amplitudeBounds'] = [options['lower'], options['upper']]
    if start is None or end is None or end <= start:
        return result
    events = defaultdict(list)
    events[start]; events[end]
    identifier = 0

    def add(a, b, kind, value=None):
        nonlocal identifier
        a, b = max(a, start), min(b, end)
        if b <= a:
            return
        identifier += 1
        events[a].append((identifier, (kind, value)))
        events[b].append((identifier, None))

    for item in bins:
        add(item['start'], item['end'], 'bin', (item['direction'], item['bin']))
    for item in invalid:
        add(item['start'], item['end'], 'quality')
    points = [(p['sequence'], p['value']) if isinstance(p, dict) else p[:2] for p in filtered]
    if fixed:
        for index, (x, y) in enumerate(points):
            if not all(math.isfinite(v) for v in (x, y)) or options['lower'] <= y <= options['upper']:
                continue
            # Classify the actual sample, not an interpolated threshold crossing.
            # In particular, a sample exactly on either bound stays in range.
            following = points[index + 1][0] if index + 1 < len(points) else x + 1
            stop = following if math.isfinite(following) and 0 < following - x <= gap else x + 1
            add(x, stop, 'range')
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if not all(math.isfinite(v) for v in (x0, y0, x1, y1)) or not 0 < x1-x0 <= gap:
            continue
        add(x0, x1, 'available')
    active = {}
    positions = sorted(events)
    for a, b in zip(positions, positions[1:]):
        for key, value in events[a]:
            if value is None:
                active.pop(key, None)
            else:
                active[key] = value
        groups = defaultdict(list)
        for kind, value in active.values():
            groups[kind].append(value)
        status, direction, number = 'unassigned', None, None
        if groups['quality'] or groups['range']:
            status = 'excluded'
        elif groups['available'] and groups['bin']:
            status = 'valid'
            direction, number = groups['bin'][0]
        item = dict(start=a, end=b, status=status, direction=direction, bin=number)
        if status == 'excluded':
            item['exclusion'] = 'quality' if groups['quality'] else 'range'
        previous = result['intervals'][-1] if result['intervals'] else None
        if previous and previous['end'] == a and all(previous.get(k) == item.get(k) for k in ('status','direction','bin','exclusion')):
            previous['end'] = b
        else:
            result['intervals'].append(item)
    return result


def build_binning_data(filtered, bins, invalid, options, start, end, fs=50, gap=25):
    """v5: bins, quality/range exclusions and unassigned original-array intervals."""
    timeline = build_binning_timeline(filtered, bins, invalid, options, start, end, fs, gap)
    groups = {direction:[[] for _ in range(timeline['totalBins']//2)] for direction in ('inhale','exhale')}
    result = {'version':5, 'inhaleRising':timeline['inhaleRising'],
              'bins':groups, 'excluded':{'quality':[], 'range':[]}, 'unassigned':[]}
    sequences = [p['sequence'] if isinstance(p, dict) else p[0] for p in filtered]

    def append(group, a, b):
        if group and group[-1][1] == a:
            group[-1][1] = b
        else:
            group.append([a, b])

    for row in timeline['intervals']:
        a, b = bisect_left(sequences, row['start']), bisect_left(sequences, row['end'])
        if b <= a:
            continue
        if row['status'] == 'valid':
            append(groups[row['direction']][row['bin']-1], a, b)
        elif row['status'] == 'excluded':
            append(result['excluded'][row['exclusion']], a, b)
        else:
            append(result['unassigned'], a, b)
    return result
