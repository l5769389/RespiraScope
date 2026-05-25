from fastapi.testclient import TestClient
import pytest

from ct_breath.app import create_app
from ct_breath.breath_process.breath_process_manager import BreathProcessSystem
from ct_breath.breath_process.data_manager import DataQueueManager
from ct_breath.breath_process.record_manager import RecordManager
from ct_breath.breath_process.signal_quality import (
    QUALITY_ARTIFACT,
    QUALITY_LOW_AMPLITUDE,
    analyze_signal_quality_batch,
)
from ct_breath.config import AppConfig
from tests.fixtures.signal_samples import cough_artifact_sample, low_amplitude_sample


def test_queue_manager_tracks_dropped_raw_points_and_high_watermark():
    manager = DataQueueManager()

    for index in range(1005):
        manager.handle_data(index, 500)

    status = manager.status()

    assert status["sizes"]["raw"] == 1000
    assert status["dropped"]["raw"] == 5
    assert status["high_watermark"]["raw"] == 1000


def test_queue_manager_keeps_recent_snapshot_for_new_clients():
    manager = DataQueueManager()

    for index in range(2105):
        manager.handle_data(index, 500)
        manager.handle_filtered_data([index], [501])
    manager.handle_peak({"sequence": 2050, "value": 540})
    manager.handle_valley({"sequence": 2060, "value": 460})
    manager.handle_metrics({"bpm": 12.0})

    messages = manager.snapshot_messages()
    by_type = {message["type"]: message["data"] for message in messages}

    assert by_type["raw"][0][0] == 105
    assert by_type["filtered"][0][0] == 105
    assert by_type["peak"] == [[2050, 540]]
    assert by_type["valley"] == [[2060, 460]]
    assert by_type["metrics"] == [{"bpm": 12.0}]


def test_signal_quality_detects_cough_artifact_sample():
    events = analyze_signal_quality_batch(cough_artifact_sample(), sampling_rate=50)

    assert any(event["quality"] == QUALITY_ARTIFACT for event in events)


def test_signal_quality_detects_low_amplitude_sample():
    events = analyze_signal_quality_batch(low_amplitude_sample(), sampling_rate=50)

    assert any(event["quality"] == QUALITY_LOW_AMPLITUDE for event in events)


def test_stream_status_exposes_queue_stats_and_signal_quality():
    client = TestClient(create_app(AppConfig(enable_mock_signal=False, enable_front_console=False)))

    response = client.get("/stream/status")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert "queue_stats" in payload
    assert "dropped" in payload["queue_stats"]
    assert "signal_quality" in payload


def test_stop_receive_returns_stopped_stream_state():
    client = TestClient(create_app(AppConfig(enable_mock_signal=False, enable_front_console=False)))

    response = client.post("/stopReceive")

    assert response.status_code == 200
    assert response.json()["data"]["stream"]["state"] == "stopped"


def test_record_save_returns_clear_error_when_record_is_not_ready(monkeypatch):
    client = TestClient(create_app(AppConfig(enable_mock_signal=False, enable_front_console=False)))

    async def fake_save_record(folder_path):
        raise ValueError("No recording has been started")

    from ct_breath.breath_process import breath_process_manager

    monkeypatch.setattr(breath_process_manager.breath_system, "save_record", fake_save_record)

    response = client.post("/record/save")

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "No recording has been started"


def test_record_start_requires_receive_and_raw_data():
    system = BreathProcessSystem()

    with pytest.raises(ValueError, match="Receive has not been started"):
        system.start_record()

    system.is_start = True
    system.state = "running"
    with pytest.raises(ValueError, match="No raw data has been received"):
        system.start_record()

    system.record_manager.handle_data(0, 500)
    record = system.start_record()

    assert record["recording"] is True
    assert record["record_start_sequence"] == 1


def test_record_start_returns_clear_error_when_preconditions_fail(monkeypatch):
    client = TestClient(create_app(AppConfig(enable_mock_signal=False, enable_front_console=False)))

    def fake_start_record():
        raise ValueError("No raw data has been received")

    from ct_breath.breath_process import breath_process_manager

    monkeypatch.setattr(breath_process_manager.breath_system, "start_record", fake_start_record)

    response = client.post("/record/start")

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "No raw data has been received"


def test_record_end_returns_clear_error_when_not_started(monkeypatch):
    client = TestClient(create_app(AppConfig(enable_mock_signal=False, enable_front_console=False)))

    async def fake_stop_record_and_filter():
        raise ValueError("No recording has been started")

    from ct_breath.breath_process import breath_process_manager

    monkeypatch.setattr(
        breath_process_manager.breath_system,
        "stop_record_and_filter",
        fake_stop_record_and_filter,
    )

    response = client.post("/record/end")

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "No recording has been started"


def test_scan_start_and_end_return_clear_precondition_errors(monkeypatch):
    client = TestClient(create_app(AppConfig(enable_mock_signal=False, enable_front_console=False)))

    from ct_breath.breath_process import breath_process_manager

    def fake_start_scan():
        raise ValueError("Scan can only start while recording")

    def fake_stop_scan():
        raise ValueError("No active scan to stop")

    monkeypatch.setattr(breath_process_manager.breath_system, "start_scan", fake_start_scan)
    response = client.post("/scan/start")

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "Scan can only start while recording"

    monkeypatch.setattr(breath_process_manager.breath_system, "stop_scan", fake_stop_scan)
    response = client.post("/scan/end")

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "No active scan to stop"


def test_record_manager_tracks_scan_ranges_and_marks_points():
    manager = RecordManager(pre_points=2, post_points=0)
    manager.handle_data(0, 500)
    manager.handle_data(1, 501)

    manager.start_record()
    manager.handle_data(2, 502)
    scan = manager.start_scan()
    manager.handle_data(3, 503)
    manager.handle_data(4, 504)
    finished_scan = manager.stop_scan()
    manager.handle_data(5, 505)
    manager.stop_record()

    payload = manager.build_record_data(
        filter_config=manager_filter_config(),
        filtered_data=[[sequence, value + 0.5] for sequence, value in manager.raw_points_for_filter()],
        filter_status="offline",
    )

    assert scan["index"] == 1
    assert scan["start_time"].endswith("+00:00")
    assert scan["end_time"] is None
    assert "start_time_iso" not in scan
    assert finished_scan["start_sequence"] == 3
    assert finished_scan["end_sequence"] == 4
    assert finished_scan["end_time"].endswith("+00:00")
    assert "end_time_iso" not in finished_scan
    assert "start_time" not in payload
    assert "end_time" not in payload
    assert payload["record_time"]["start_time"].endswith("+00:00")
    assert payload["raw_data"][0]["timestamp"].endswith("+00:00")
    assert payload["segments"]["pre"]["start_sequence"] == 0
    assert payload["segments"]["pre"]["end_sequence"] == 1
    assert payload["segments"]["record"]["start_sequence"] == 2
    assert payload["segments"]["post"]["start_sequence"] == 6
    assert payload["scans"][0]["start_sequence"] == 3
    assert payload["scans"][0]["end_sequence"] == 4
    assert [point["segment"] for point in payload["raw_data"]] == [
        "pre",
        "pre",
        "record",
        "record",
        "record",
        "record",
    ]
    scan_points = [point for point in payload["raw_data"] if point["scan_indexes"]]
    assert [point["sequence"] for point in scan_points] == [3, 4]


def test_record_manager_reset_clears_record_and_scan_state():
    manager = RecordManager(pre_points=2, post_points=0)
    manager.handle_data(0, 500)
    manager.start_record()
    manager.start_scan()

    status = manager.reset_record()

    assert status["recording"] is False
    assert status["scan_active"] is False
    assert status["active_scan"] is None
    assert status["scans"] == []
    assert manager.latest_raw_sequence == 0
    assert list(manager.raw_record_queue) == []

    restarted = manager.start_record()
    scan = manager.start_scan()

    assert restarted["recording"] is True
    assert scan["index"] == 1
    assert manager.status()["scan_active"] is True


def test_record_reset_endpoint_clears_backend_record_state(monkeypatch):
    client = TestClient(create_app(AppConfig(enable_mock_signal=False, enable_front_console=False)))

    from ct_breath.breath_process import breath_process_manager

    manager = breath_process_manager.breath_system.record_manager
    manager.handle_data(0, 500)
    manager.start_record()
    manager.start_scan()

    response = client.post("/record/reset")

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Record reset"
    assert payload["record"]["recording"] is False
    assert payload["record"]["scan_active"] is False
    assert payload["record"]["active_scan"] is None


def test_record_end_returns_offline_filtered_record(monkeypatch):
    client = TestClient(create_app(AppConfig(enable_mock_signal=False, enable_front_console=False)))

    async def fake_stop_record_and_filter():
        return {
            "version": 2,
            "record_start_sequence": 10,
            "record_end_sequence": 20,
            "capture_start_sequence": 8,
            "capture_end_sequence": 22,
            "segments": {
                "pre": {"start_sequence": 8, "end_sequence": 9, "auxiliary": True},
                "record": {"start_sequence": 10, "end_sequence": 20, "auxiliary": False},
                "post": {"start_sequence": 21, "end_sequence": 22, "auxiliary": True},
            },
            "scans": [{"index": 1, "start_sequence": 12, "end_sequence": 15}],
            "raw_data": [{"sequence": 10, "value": 500, "segment": "record", "scan_indexes": []}],
            "filtered_data": [{"sequence": 10, "value": 501, "segment": "record", "scan_indexes": []}],
            "peak": [],
            "valley": [],
            "metrics": {"quality": "insufficient"},
            "filter_status": "offline",
        }

    from ct_breath.breath_process import breath_process_manager

    monkeypatch.setattr(breath_process_manager.breath_system, "stop_record_and_filter", fake_stop_record_and_filter)

    response = client.post("/record/end")

    assert response.status_code == 200
    payload = response.json()
    assert payload["filter_status"] == "offline"
    assert payload["segments"]["pre"]["start_sequence"] == 8
    assert payload["segments"]["post"]["end_sequence"] == 22
    assert payload["scans"][0]["start_sequence"] == 12
    assert payload["raw_data"][0]["value"] == 500
    assert payload["data"][0]["value"] == 501
    assert "scan_indexes" not in payload["raw_data"][0]
    assert "scan_indexes" not in payload["data"][0]
    assert "filter_config" not in payload
    assert "capture_start_sequence" not in payload
    assert "capture_end_sequence" not in payload


def manager_filter_config():
    from ct_breath.http.schemas import FilterConfig, normalize_filter_config

    return normalize_filter_config(FilterConfig())
