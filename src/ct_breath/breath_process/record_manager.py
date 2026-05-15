import asyncio
import json
import os
import time
from collections import deque
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from ct_breath.http.schemas import FilterConfig
from ct_breath.logger import logger


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


def iso_time(timestamp):
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


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


def annotate_points(points, start_sequence, end_sequence):
    annotated = []
    for point in points:
        item = normalize_point(point)
        sequence = point_sequence(item)
        item["segment"] = point_segment(sequence, start_sequence, end_sequence)
        annotated.append(item)
    return annotated


def sequence_range(points):
    sequences = [point_sequence(point) for point in points]
    sequences = [int(seq) for seq in sequences if seq is not None]
    if not sequences:
        return None, None
    return min(sequences), max(sequences)


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
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="file_writer")

    def start_record(self):
        now = time.time()
        self.recording = True
        self.post_recording = False
        self.record_complete = False
        self.record_start_time = now
        self.record_end_time = None
        self.record_end_sequence = None
        self.capture_end_sequence = None
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

    def stop_record(self):
        if not self.recording:
            return

        self.recording = False
        self.record_end_time = time.time()
        self.record_end_sequence = self.latest_raw_sequence

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

    async def save_record(self, filter_config: FilterConfig, folder_path=None):
        fullpath = None
        try:
            make_folder(folder_path)
            filename = f"breath_record_{int(time.time())}.json"
            fullpath = str(Path(folder_path) / filename)
        except Exception as e:
            logger.error("save_record error", e)

        raw_data = annotate_points(
            list(self.raw_record_queue),
            self.record_start_sequence,
            self.record_end_sequence,
        )
        filtered_data = annotate_points(
            list(self.filter_record_queue),
            self.record_start_sequence,
            self.record_end_sequence,
        )
        peak_data = annotate_points(
            list(self.peak_record_queue),
            self.record_start_sequence,
            self.record_end_sequence,
        )
        valley_data = annotate_points(
            list(self.valley_record_queue),
            self.record_start_sequence,
            self.record_end_sequence,
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
            "start_time": self.record_start_time,
            "end_time": self.record_end_time,
            "record_time": {
                "start_time": iso_time(self.record_start_time),
                "end_time": iso_time(self.record_end_time),
                "duration_seconds": duration,
            },
            "duration": duration,
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
            "raw_data": raw_data,
            "filtered_data": filtered_data,
            "filter_params": filter_config.model_dump(),
            "peak": peak_data,
            "valley": valley_data,
        }
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            write_file,
            record_data,
            fullpath,
        )
        logger.info(f"Saved breath record to {fullpath}")
        return fullpath

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
                "redundant": True,
            },
            SEGMENT_RECORD: {
                "start_sequence": self.record_start_sequence,
                "end_sequence": self.record_end_sequence,
                "redundant": False,
            },
            SEGMENT_POST: {
                "start_sequence": (
                    self.record_end_sequence + 1
                    if self.record_end_sequence is not None
                    else None
                ),
                "end_sequence": capture_end_sequence,
                "redundant": True,
            },
        }
