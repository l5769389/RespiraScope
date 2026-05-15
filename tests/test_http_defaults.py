from fastapi.testclient import TestClient

from ct_breath.app import create_app
from ct_breath.config import AppConfig
from ct_breath.breath_process import breath_process_manager


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
