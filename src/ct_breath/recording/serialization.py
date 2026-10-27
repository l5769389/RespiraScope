"""Version 6 disk format: one compact bin representation, indexed into filtered."""


def compact_points(points):
    result = []
    for point in points:
        item = [point['sequence'], point['value']]
        if point.get('timestamp') is not None:
            item.append(point['timestamp'])
        result.append(item)
    return result


def compact_extrema(points):
    result = []
    for point in points:
        item = {'sequence': point['sequence'], 'value': point['value']}
        if point.get('amplitudeRange') in ('above', 'below'):
            item['amplitudeRange'] = point['amplitudeRange']
        result.append(item)
    return result


def compact_record_data(payload, time_filter_config=None):
    """Keep each measurement/range once; derived labels are rebuilt on import."""
    result = {
        'version': 6,
        'startTime': payload['record_time']['start_time'],
        'endTime': payload['record_time']['end_time'],
        'startSeq': payload['record_start_sequence'],
        'endSeq': payload['record_end_sequence'],
        'analysis': payload['analysis'],
        'filterConfig': payload['filter_params'],
        'filterStatus': payload['filter_status'],
        'raw': compact_points(payload['raw_data']),
        'filtered': compact_points(payload['filtered_data']),
        'peaks': compact_extrema(payload['peak']),
        'valleys': compact_extrema(payload['valley']),
    }
    scans = []
    if 'binningData' in payload:
        result['binningData'] = payload['binningData']
    if payload.get('processingQuality') is not None:
        result['processingQuality'] = payload['processingQuality']
    for scan in payload['scans']:
        item = {target: scan[source] for source, target in (
            ('index', 'index'), ('start_sequence', 'startSeq'), ('end_sequence', 'endSeq'),
            ('start_time', 'startTime'), ('end_time', 'endTime'),
        ) if scan.get(source) is not None}
        if scan.get('auto_closed'):
            item['autoClosed'] = True
        scans.append(item)
    if scans:
        result['scans'] = scans
    return result
