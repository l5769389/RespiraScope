from datetime import datetime, timezone


def iso_time(timestamp):
    if timestamp is None:
        return None
    if isinstance(timestamp, str):
        return timestamp
    return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).isoformat()
