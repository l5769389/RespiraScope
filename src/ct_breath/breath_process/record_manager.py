import asyncio
import json
import os
import time
from collections import deque
from concurrent.futures.thread import ThreadPoolExecutor
from pathlib import Path

from ct_breath.http.schemas import FilterConfig
from ct_breath.logger import logger
from ct_breath.time_utils import iso_time


MAX_RAW_RECORD_POINTS = 50 * 60 * 20
MAX_MARKER_RECORD_POINTS = 50 * 60 * 10
SEGMENT_PRE = "pre"
SEGMENT_RECORD = "record"
SEGMENT_POST = "post"


def make_folder(folder_path):
    output_dir = Path(folder_path)
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def write_file(record_data, fullpath):
    with open(fullpath, "w", encoding="utf-8") as f:
        json.dump(record_data, f, ensure_ascii=False, indent=2)


def point_sequence(point):
    if isinstance(point, dict):
        return point.get("sequence")
    if isinstance(point, (list, tuple)) and point:
        return point[0]
    return None


def normalize_point(point):
    if isinstance(point, dict):
        return dict(point)
    if isinstance(point, (list, tuple)) and len(point) >= 2:
        return {
            "sequence": point[0],
            "value": point[1],
        }
    return {
        "sequence": point_sequence(point),
        "value": None,
    }


def point_segment(sequence, start_sequence, end_sequence):
    if sequence is None:
        return SEGMENT_RECORD
    if start_sequence is not None and sequence < start_sequence:
        return SEGMENT_PRE
    if end_sequence is not None and sequence > end_sequence:
        return SEGMENT_POST
    return SEGMENT_RECORD


def point_scan_indexes(sequence, scans):
    if sequence is None:
        return []

    matched = []
    for scan in scans or []:
        start_sequence = scan.get("start_sequence")
        end_sequence = scan.get("end_sequence")
        if start_sequence is None or end_sequence is None:
            continue
        if int(start_sequence) <= int(sequence) <= int(end_sequence):
            matched.append(scan.get("index"))
    return matched


def annotate_points(points, start_sequence, end_sequence, scans=None):
    annotated = []
    for point in points:
        item = normalize_point(point)
        if item.get("timestamp") is not None:
            item["timestamp"] = iso_time(item["timestamp"])
        sequence = point_sequence(item)
        item["segment"] = point_segment(sequence, start_sequence, end_sequence)
        item["scan_indexes"] = point_scan_indexes(sequence, scans)
        annotated.append(item)
    return annotated


def sequence_range(points):
    sequences = [point_sequence(point) for point in points]
    sequences = [int(seq) for seq in sequences if seq is not None]
    if not sequences:
        return None, None
    return min(sequences), max(sequences)


def scan_snapshot(scan):
    if scan is None:
        return None

    item = dict(scan)
    start_time = item.get("start_time")
    end_time = item.get("end_time")
    item["start_time"] = start_time if isinstance(start_time, str) else iso_time(start_time)
    item["end_time"] = end_time if isinstance(end_time, str) else iso_time(end_time)
    item.pop("start_time_iso", None)
    item.pop("end_time_iso", None)
    return item


class RecordManager:
    def __init__(self, pre_points: int = 0, post_points: int = 0):
        self.pre_points = max(0, int(pre_points))
        self.post_points = max(0, int(post_points))
        self.recording = False
        self.post_recording = False
        self.record_complete = False
        self.raw_pre_buffer = deque(maxlen=max(1, self.pre_points))
        self.filter_pre_buffer = deque(maxlen=max(1, self.pre_points))
        self.peak_pre_buffer = deque(maxlen=max(1, self.pre_points))
        self.valley_pre_buffer = deque(maxlen=max(1, self.pre_points))
        self.raw_record_queue = deque(maxlen=MAX_RAW_RECORD_POINTS)
        self.filter_record_queue = deque(maxlen=MAX_RAW_RECORD_POINTS)
        self.peak_record_queue = deque(maxlen=MAX_MARKER_RECORD_POINTS)
        self.valley_record_queue = deque(maxlen=MAX_MARKER_RECORD_POINTS)
        self.latest_raw_sequence = None
        self.record_start_time = None
        self.record_end_time = None
        self.record_start_sequence = None
        self.record_end_sequence = None
        self.capture_start_sequence = None
        self.capture_end_sequence = None
        self.scans = []
        self.active_scan = None
        self.next_scan_index = 1
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="file_writer")

    def start_record(self):
        if self.recording:
            return self.status()

        now = time.time()
        self.recording = True
        self.post_recording = False
        self.record_complete = False
        self.record_start_time = now
        self.record_end_time = None
        self.record_end_sequence = None
        self.capture_end_sequence = None
        self.scans.clear()
        self.active_scan = None
        self.next_scan_index = 1
        self.raw_record_queue.clear()
        self.filter_record_queue.clear()
        self.peak_record_queue.clear()
        self.valley_record_queue.clear()

        if self.latest_raw_sequence is None:
            self.record_start_sequence = None
            self.capture_start_sequence = None
        else:
            self.record_start_sequence = int(self.latest_raw_sequence) + 1
            self.capture_start_sequence = max(0, self.record_start_sequence - self.pre_points)

        self._copy_pre_buffers()
        logger.info(
            "Started breath recording with pre=%s post=%s start_seq=%s capture_start=%s",
            self.pre_points,
            self.post_points,
            self.record_start_sequence,
            self.capture_start_sequence,
        )
        return self.status()

    def reset_record(self):
        self.recording = False
        self.post_recording = False
        self.record_complete = False
        self.record_start_time = None
        self.record_end_time = None
        self.record_start_sequence = None
        self.record_end_sequence = None
        self.capture_start_sequence = None
        self.capture_end_sequence = None
        self.scans.clear()
        self.active_scan = None
        self.next_scan_index = 1
        self.raw_record_queue.clear()
        self.filter_record_queue.clear()
        self.peak_record_queue.clear()
        self.valley_record_queue.clear()
        return self.status()

    def stop_record(self):
        if not self.recording:
            return

        self.recording = False
        self.record_end_time = time.time()
        self.record_end_sequence = self.latest_raw_sequence
        if self.active_scan is not None:
            self._finish_active_scan(self.record_end_sequence, auto_closed=True)

        if self.record_start_sequence is None:
            self.record_start_sequence = self.record_end_sequence
        if self.capture_start_sequence is None:
            self.capture_start_sequence = self.record_start_sequence

        if self.record_end_sequence is None or self.post_points == 0:
            self.capture_end_sequence = self.record_end_sequence
            self.post_recording = False
            self.record_complete = True
        else:
            self.capture_end_sequence = int(self.record_end_sequence) + self.post_points
            self.post_recording = True
            self.record_complete = False

        duration = (
            self.record_end_time - self.record_start_time
            if self.record_start_time and self.record_end_time
            else 0
        )
        logger.info(
            "Stopped breath recording. Duration: %.2fs, end_seq=%s, capture_end=%s",
            duration,
            self.record_end_sequence,
            self.capture_end_sequence,
        )

    def start_scan(self):
        if not self.recording:
            raise ValueError("Scan can only start while recording")
        if self.active_scan is not None:
            raise ValueError("A scan is already active")

        now = time.time()
        start_sequence = None
        if self.latest_raw_sequence is not None:
            start_sequence = int(self.latest_raw_sequence) + 1

        self.active_scan = {
            "index": self.next_scan_index,
            "start_time": now,
            "end_time": None,
            "start_sequence": start_sequence,
            "end_sequence": None,
            "auto_closed": False,
        }
        self.next_scan_index += 1
        logger.info(
            "Started scan %s at sequence %s",
            self.active_scan["index"],
            self.active_scan["start_sequence"],
        )
        return scan_snapshot(self.active_scan)

    def stop_scan(self):
        if self.active_scan is None:
            raise ValueError("No active scan to stop")
        return self._finish_active_scan(self.latest_raw_sequence)

    def _finish_active_scan(self, end_sequence=None, auto_closed=False):
        if self.active_scan is None:
            return None

        now = time.time()
        scan = self.active_scan
        if scan.get("start_sequence") is None:
            scan["start_sequence"] = end_sequence
        scan["end_sequence"] = end_sequence
        if (
            scan.get("start_sequence") is not None
            and scan.get("end_sequence") is not None
            and int(scan["end_sequence"]) < int(scan["start_sequence"])
        ):
            scan["end_sequence"] = scan["start_sequence"]
        scan["end_time"] = now
        scan["auto_closed"] = bool(auto_closed)
        self.scans.append(dict(scan))
        self.active_scan = None
        logger.info(
            "Stopped scan %s at sequence %s",
            scan["index"],
            scan["end_sequence"],
        )
        return scan_snapshot(scan)

    async def save_record(self, filter_config: FilterConfig, folder_path=None):
        if self.record_start_time is None:
            raise ValueError("No recording has been started")
        if self.recording:
            raise ValueError("Recording has not ended")
        if self.post_recording:
            raise ValueError("Recording is still collecting post-record padding")
        if not self.raw_record_queue and not self.filter_record_queue:
            raise ValueError("No record data is available to save")

        fullpath = None
        try:
            make_folder(folder_path)
            filename = f"breath_record_{int(time.time())}.json"
            fullpath = str(Path(folder_path) / filename)
        except Exception as e:
            logger.error("save_record error: %s", e)
            raise ValueError(f"Invalid record folder: {folder_path}") from e

        record_data = self.build_record_data(filter_config)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            write_file,
            record_data,
            fullpath,
        )
        logger.info(f"Saved breath record to {fullpath}")
        return fullpath

    def build_record_data(
        self,
        filter_config: FilterConfig,
        filtered_data=None,
        peak_data=None,
        valley_data=None,
        metrics=None,
        filter_status="live",
    ):
        raw_data = annotate_points(
            list(self.raw_record_queue),
            self.record_start_sequence,
            self.record_end_sequence,
            self.scans,
        )
        filtered_data = annotate_points(
            list(self.filter_record_queue) if filtered_data is None else filtered_data,
            self.record_start_sequence,
            self.record_end_sequence,
            self.scans,
        )
        peak_data = annotate_points(
            list(self.peak_record_queue) if peak_data is None else peak_data,
            self.record_start_sequence,
            self.record_end_sequence,
            self.scans,
        )
        valley_data = annotate_points(
            list(self.valley_record_queue) if valley_data is None else valley_data,
            self.record_start_sequence,
            self.record_end_sequence,
            self.scans,
        )
        raw_start, raw_end = sequence_range(raw_data)
        filtered_start, filtered_end = sequence_range(filtered_data)
        duration = (
            self.record_end_time - self.record_start_time
            if self.record_start_time and self.record_end_time
            else None
        )
        capture_start_sequence = self.capture_start_sequence
        if capture_start_sequence is None:
            capture_start_sequence = raw_start if raw_start is not None else filtered_start
        capture_end_sequence = self.capture_end_sequence
        if capture_end_sequence is None:
            capture_end_sequence = raw_end if raw_end is not None else filtered_end
        elif raw_end is not None and not self.record_complete and raw_end < capture_end_sequence:
            capture_end_sequence = raw_end

        record_data = {
            "version": 2,
            "record_time": {
                "start_time": iso_time(self.record_start_time),
                "end_time": iso_time(self.record_end_time),
                "duration_seconds": duration,
            },
            "record_start_sequence": self.record_start_sequence,
            "record_end_sequence": self.record_end_sequence,
            "capture_start_sequence": capture_start_sequence,
            "capture_end_sequence": capture_end_sequence,
            "start_sequence": self.record_start_sequence,
            "end_sequence": self.record_end_sequence,
            "segments": self._segments(capture_start_sequence, capture_end_sequence),
            "record_padding": {
                "pre_points": self.pre_points,
                "post_points": self.post_points,
            },
            "scans": [scan_snapshot(scan) for scan in self.scans],
            "raw_data": raw_data,
            "filtered_data": filtered_data,
            "filter_params": filter_config.model_dump(),
            "filter_status": filter_status,
            "peak": peak_data,
            "valley": valley_data,
            "metrics": metrics,
        }
        return record_data

    def raw_points_for_filter(self):
        points = []
        for point in self.raw_record_queue:
            item = normalize_point(point)
            sequence = point_sequence(item)
            value = item.get("value")
            if sequence is None or value is None:
                continue
            points.append([int(sequence), float(value)])
        return sorted(points, key=lambda item: item[0])

    def handle_data(self, sequence_number, sensor_val):
        self.latest_raw_sequence = sequence_number
        point = {
            "sequence": sequence_number,
            "value": sensor_val,
            "timestamp": time.time(),
        }
        self.raw_pre_buffer.append(point)

        if self.recording and self.record_start_sequence is None:
            self.record_start_sequence = sequence_number
            self.capture_start_sequence = sequence_number
        if self.active_scan is not None and self.active_scan.get("start_sequence") is None:
            self.active_scan["start_sequence"] = sequence_number

        if self._should_capture_sequence(sequence_number):
            self.raw_record_queue.append(point)

        if self.post_recording and self.capture_end_sequence is not None:
            if sequence_number >= self.capture_end_sequence:
                self.post_recording = False
                self.record_complete = True

    def handle_filtered_data(self, sequences, values):
        now = time.time()
        for seq, val in zip(sequences, values):
            point = {
                "sequence": seq,
                "value": val,
                "timestamp": now,
            }
            self.filter_pre_buffer.append(point)
            if self._should_capture_sequence(seq):
                self.filter_record_queue.append(point)

    def handle_peak(self, peak_data):
        point = normalize_point(peak_data)
        self.peak_pre_buffer.append(point)
        if self._should_capture_sequence(point_sequence(point)):
            self.peak_record_queue.append(point)

    def handle_valley(self, valley_data):
        point = normalize_point(valley_data)
        self.valley_pre_buffer.append(point)
        if self._should_capture_sequence(point_sequence(point)):
            self.valley_record_queue.append(point)

    def _copy_pre_buffers(self):
        if self.capture_start_sequence is None or self.record_start_sequence is None:
            return
        for point in self._points_in_range(
            self.raw_pre_buffer,
            self.capture_start_sequence,
            self.record_start_sequence - 1,
        ):
            self.raw_record_queue.append(point)
        for point in self._points_in_range(
            self.filter_pre_buffer,
            self.capture_start_sequence,
            self.record_start_sequence - 1,
        ):
            self.filter_record_queue.append(point)
        for point in self._points_in_range(
            self.peak_pre_buffer,
            self.capture_start_sequence,
            self.record_start_sequence - 1,
        ):
            self.peak_record_queue.append(point)
        for point in self._points_in_range(
            self.valley_pre_buffer,
            self.capture_start_sequence,
            self.record_start_sequence - 1,
        ):
            self.valley_record_queue.append(point)

    def _points_in_range(self, points, start_sequence, end_sequence):
        selected = []
        for point in points:
            sequence = point_sequence(point)
            if sequence is None:
                continue
            if start_sequence <= sequence <= end_sequence:
                selected.append(point)
        return selected

    def _should_capture_sequence(self, sequence):
        if sequence is None:
            return False
        if self.capture_start_sequence is None:
            return False
        if sequence < self.capture_start_sequence:
            return False
        if self.capture_end_sequence is not None and sequence > self.capture_end_sequence:
            return False
        return self.recording or self.post_recording or self.record_start_sequence is not None

    def _segments(self, capture_start_sequence, capture_end_sequence):
        return {
            SEGMENT_PRE: {
                "start_sequence": capture_start_sequence,
                "end_sequence": (
                    self.record_start_sequence - 1
                    if self.record_start_sequence is not None
                    else None
                ),
                "auxiliary": True,
            },
            SEGMENT_RECORD: {
                "start_sequence": self.record_start_sequence,
                "end_sequence": self.record_end_sequence,
                "auxiliary": False,
            },
            SEGMENT_POST: {
                "start_sequence": (
                    self.record_end_sequence + 1
                    if self.record_end_sequence is not None
                    else None
                ),
                "end_sequence": capture_end_sequence,
                "auxiliary": True,
            },
        }

    def status(self):
        return {
            "pre_points": self.pre_points,
            "post_points": self.post_points,
            "recording": self.recording,
            "post_recording": self.post_recording,
            "record_complete": self.record_complete,
            "record_start_sequence": self.record_start_sequence,
            "record_end_sequence": self.record_end_sequence,
            "capture_start_sequence": self.capture_start_sequence,
            "capture_end_sequence": self.capture_end_sequence,
            "scan_active": self.active_scan is not None,
            "active_scan": scan_snapshot(self.active_scan),
            "scans": [scan_snapshot(scan) for scan in self.scans],
        }
