"""Measured half breaths and conservative, extremum-anchored amplitude tails.

Keep this logic in sync with web/monitor/modules/binning-segments.js.
No samples or public peak/valley annotations are changed here.
"""
import math


def continuous_runs(data, invalid, gap):
    current = []
    for point in data:
        x, y = point
        if not math.isfinite(x) or not math.isfinite(y) or any(i['start'] <= x < i['end'] for i in invalid):
            if current:
                yield current
                current = []
            continue
        if current and (not 0 < x-current[-1][0] <= gap or
                        any(current[-1][0] < i['end'] and x >= i['start'] for i in invalid)):
            yield current
            current = []
        current.append(point)
    if current:
        yield current


def clear_leg(points, threshold, min_span):
    if len(points) < 3 or abs(points[-1][0]-points[0][0]) < min_span:
        return False
    distance = abs(points[-1][1]-points[0][1])
    variation = sum(abs(b[1]-a[1]) for a,b in zip(points, points[1:]))
    return distance >= threshold and distance >= .9*variation


def consistent_direction(points, rising, threshold):
    """Reject a missing pair of turns, allowing small local fluctuations."""
    sign = 1 if rising else -1
    best = sign*points[0][1]
    for _, value in points[1:]:
        value *= sign
        best = max(best, value)
        if best-value >= threshold:
            return False
    return True


def missing_turn(points, left, right, kind, threshold, min_span):
    """Recover one observed turn only when both sides have a clear direction."""
    values = [p[1] for p in points[left:right+1]]
    target = min(values) if kind == 'peak' else max(values)
    hits = [left+i for i,y in enumerate(values) if y == target]
    first, last = hits[0], hits[-1]
    # A long plateau or repeated equal extremes does not locate a unique turn.
    if (first == left or last == right or last-first+1 != len(hits)
            or points[last][0]-points[first][0] > min_span):
        return None
    index = (first+last)//2
    if (clear_leg(points[left:index+1], threshold, min_span)
            and clear_leg(points[index:right+1], threshold, min_span)):
        return index
    return None


def edge_leg(points, index, step, kind, threshold, min_span):
    """Walk outward from a trusted extremum; stop at the first clear reversal."""
    sign = -1 if kind == 'peak' else 1
    best = index
    for j in range(index+step, len(points) if step > 0 else -1, step):
        if sign*(points[j][1]-points[best][1]) > 0:
            best = j
        elif sign*(points[best][1]-points[j][1]) >= threshold:
            break
    a,b = sorted((index,best))
    segment = points[a:b+1]
    return segment if clear_leg(segment, threshold, min_span) else None


def binning_segments(data, events, invalid, gap, fixed, sampling_rate):
    for points in continuous_runs(data, invalid, gap):
        lookup = {p[0]:i for i,p in enumerate(points)}
        anchors = [(lookup[x],kind) for x,kind in events if x in lookup]
        if not anchors:
            continue
        values = sorted(p[1] for p in points)
        span = values[int((len(values)-1)*.95)]-values[int((len(values)-1)*.05)]
        threshold = max(1., .1*span)
        min_span = max(1., .2*sampling_rate)
        recovered = []
        for (a,kind),(b,next_kind) in zip(anchors,anchors[1:]):
            recovered.append((a,kind))
            if kind == next_kind and b > a:
                turn = missing_turn(points,a,b,kind,threshold,min_span)
                if turn is not None:
                    recovered.append((turn,'valley' if kind == 'peak' else 'peak'))
        recovered.append(anchors[-1])
        if fixed:
            a,kind = recovered[0]
            segment = edge_leg(points,a,-1,kind,threshold,min_span)
            if segment:
                yield segment, kind == 'peak'
        for (a,kind),(b,next_kind) in zip(recovered,recovered[1:]):
            if kind == next_kind or b <= a:
                continue
            rising = kind == 'valley'
            segment = points[a:b+1]
            if (points[b][1] != points[a][1] and (points[b][1] > points[a][1]) == rising
                    and consistent_direction(segment, rising, threshold)):
                yield segment, rising
        if fixed:
            a,kind = recovered[-1]
            segment = edge_leg(points,a,1,kind,threshold,min_span)
            if segment:
                yield segment, kind == 'valley'
