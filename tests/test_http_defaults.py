import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from ct_breath.app import create_app
from ct_breath.config import AppConfig
from ct_breath.breath_process import breath_process_manager
from ct_breath.breath_process.breath_process_manager import BreathProcessSystem
from ct_breath.session import SessionManager


def test_start_receive_accepts_empty_body_and_uses_wide_defaults():
    client = TestClient(create_app(AppConfig(enable_mock_signal=False, enable_front_console=False)))

    response = client.post("/startReceive")

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["low_bpm"] == 6
    assert payload["config"]["high_bpm"] == 40
    assert payload["config"]["lowpass_cutoff"] == 6 / 60
    assert payload["config"]["highpass_cutoff"] == 40 / 60


def test_set_filter_accepts_empty_json_and_uses_wide_defaults():
    client = TestClient(create_app(AppConfig(enable_mock_signal=False, enable_front_console=False)))

    response = client.post("/setRTFilterParams", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["low_bpm"] == 6
    assert payload["config"]["high_bpm"] == 40


def test_apply_filter_accepts_empty_body_and_returns_empty_result():
    client = TestClient(create_app(AppConfig(enable_mock_signal=False, enable_front_console=False)))

    response = client.post("/applyFilter")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"] == []
    assert payload["peak"] == []
    assert payload["valley"] == []
    assert payload["metrics"]["quality"] == "insufficient"
    assert payload["filter_config"]["low_bpm"] == 6
    assert payload["filter_config"]["high_bpm"] == 40


def test_record_save_accepts_empty_body_and_uses_default_folder(monkeypatch):
    client = TestClient(create_app(AppConfig(enable_mock_signal=False, enable_front_console=False)))
    captured = {}

    async def fake_save_record(folder_path):
        captured["folder_path"] = folder_path
        return "D:/ct/breath-file/breath_record_test.json"

    monkeypatch.setattr(breath_process_manager.breath_system, "save_record", fake_save_record)

    response = client.post("/record/save")

    assert response.status_code == 200
    assert captured["folder_path"] == "D:/ct/breath-file"
    assert response.json()["data"]["file_path"] == "D:/ct/breath-file/breath_record_test.json"


def test_mock_config_is_isolated_by_browser_session():
    client = TestClient(create_app(AppConfig(enable_mock_signal=True, enable_front_console=False)))
    session_a = {"X-RespiraScope-Session": "session-a"}
    session_b = {"X-RespiraScope-Session": "session-b"}

    response = client.post("/mock/config", headers=session_a, json={"scenario": "shallow"})
    assert response.status_code == 200

    response_a = client.get("/mock/config", headers=session_a)
    response_b = client.get("/mock/config", headers=session_b)

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert response_a.json()["data"]["scenario"] == "shallow"
    assert response_b.json()["data"]["scenario"] == "normal"


def test_filter_config_is_isolated_by_browser_session():
    client = TestClient(create_app(AppConfig(enable_mock_signal=True, enable_front_console=False)))
    session_a = {"X-RespiraScope-Session": "session-a"}
    session_b = {"X-RespiraScope-Session": "session-b"}

    response = client.post(
        "/setRTFilterParams",
        headers=session_a,
        json={"low_bpm": 8, "high_bpm": 32},
    )
    assert response.status_code == 200

    response_a = client.get("/stream/status", headers=session_a)
    response_b = client.get("/stream/status", headers=session_b)

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert response_a.json()["data"]["filter_config"]["low_bpm"] == 8
    assert response_b.json()["data"]["filter_config"]["low_bpm"] == 6


def test_session_record_save_uses_session_temp_folder(monkeypatch, tmp_path):
    app = create_app(
        AppConfig(
            enable_mock_signal=True,
            enable_front_console=False,
            record_storage_root=tmp_path,
        )
    )
    client = TestClient(app)
    captured = []

    async def fake_save_record(self, folder_path):
        captured.append(Path(folder_path))
        return str(Path(folder_path) / "breath_record_test.json")

    monkeypatch.setattr(BreathProcessSystem, "save_record", fake_save_record)

    response = client.post(
        "/record/save",
        headers={"X-RespiraScope-Session": "session-a"},
        json={"folder_path": "D:/ct/escape-attempt"},
    )
    response_b = client.post(
        "/record/save",
        headers={"X-RespiraScope-Session": "session-b"},
        json={"folder_path": "D:/ct/escape-attempt"},
    )

    assert response.status_code == 200
    assert response_b.status_code == 200
    assert captured == [tmp_path / "session-a", tmp_path / "session-b"]
    assert response.json()["data"]["file_path"] == str(tmp_path / "session-a" / "breath_record_test.json")
    assert response_b.json()["data"]["file_path"] == str(tmp_path / "session-b" / "breath_record_test.json")


def test_session_cleanup_removes_temp_record_folder(tmp_path):
    manager = SessionManager(
        AppConfig(
            enable_mock_signal=True,
            enable_front_console=False,
            record_storage_root=tmp_path,
        )
    )
    manager.get_session("session-a")
    record_folder = manager.record_folder("session-a")
    record_file = record_folder / "breath_record_test.json"
    record_file.write_text("{}", encoding="utf-8")

    asyncio.run(manager.stop_session("session-a"))

    assert not record_folder.exists()
