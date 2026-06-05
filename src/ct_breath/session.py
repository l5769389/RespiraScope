import asyncio
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, Request

from ct_breath.breath_process.breath_process_manager import BreathProcessSystem
from ct_breath.config import AppConfig
from ct_breath.mock_sensor.breath_simulator import MockBreathController, mock_breath_controller
from ct_breath.session_ids import SESSION_HEADER, SESSION_QUERY_PARAM, normalize_session_id
from ct_breath.socket_io_service import (
    remove_snapshot_provider,
    send_socket_io_message,
    set_snapshot_provider,
)


@dataclass
class ManagedSession:
    session_id: str
    system: BreathProcessSystem
    mock_controller: MockBreathController
    last_seen: float


class SessionManager:
    def __init__(self, app_config: AppConfig):
        self.app_config = app_config
        self._sessions: dict[str, ManagedSession] = {}

    def get_system(self, session_id: str) -> BreathProcessSystem:
        return self.get_session(session_id).system

    def get_mock_controller(self, session_id: str) -> MockBreathController:
        return self.get_session(session_id).mock_controller

    def record_folder(self, session_id: str) -> Path:
        normalized = normalize_session_id(session_id)
        if not normalized:
            raise ValueError("Session id is required")
        root = Path(self.app_config.record_storage_root).resolve()
        session_folder = (root / normalized).resolve()
        if not session_folder.is_relative_to(root):
            raise ValueError("Invalid RespiraScope session record folder")
        session_folder.mkdir(parents=True, exist_ok=True)
        return session_folder

    def touch(self, session_id: str):
        normalized = normalize_session_id(session_id)
        if not normalized:
            return
        session = self._sessions.get(normalized)
        if session:
            session.last_seen = time.time()

    def get_session(self, session_id: str) -> ManagedSession:
        normalized = normalize_session_id(session_id)
        if not normalized:
            raise ValueError("Session id is required")

        session = self._sessions.get(normalized)
        if session is not None:
            session.last_seen = time.time()
            return session

        mock_controller = MockBreathController()

        async def send_session_message(message: dict, _session_id=normalized):
            await send_socket_io_message(message, session_id=_session_id)

        def register_snapshot_provider(provider, _session_id=normalized):
            set_snapshot_provider(provider, session_id=_session_id)

        system = BreathProcessSystem(
            self.app_config,
            session_id=normalized,
            send_message=send_session_message,
            snapshot_provider_registrar=register_snapshot_provider,
            mock_config_provider=mock_controller.get_config,
            use_direct_mock=self.app_config.enable_mock_signal,
        )
        session = ManagedSession(
            session_id=normalized,
            system=system,
            mock_controller=mock_controller,
            last_seen=time.time(),
        )
        self._sessions[normalized] = session
        return session

    async def stop_session(self, session_id: str):
        normalized = normalize_session_id(session_id)
        if not normalized:
            return
        session = self._sessions.pop(normalized, None)
        if session is None:
            return
        remove_snapshot_provider(normalized)
        await session.system.stop_system()
        self._remove_record_folder(normalized)

    async def stop_all(self):
        for session_id in list(self._sessions):
            await self.stop_session(session_id)

    async def cleanup_idle_sessions(self):
        while True:
            await asyncio.sleep(60)
            await self.stop_expired_sessions()

    async def stop_expired_sessions(self):
        timeout = max(60, int(self.app_config.session_idle_timeout_seconds))
        now = time.time()
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if now - session.last_seen >= timeout
        ]
        for session_id in expired:
            await self.stop_session(session_id)

    def _remove_record_folder(self, session_id: str):
        root = Path(self.app_config.record_storage_root).resolve()
        session_folder = (root / session_id).resolve()
        if not session_folder.is_relative_to(root):
            return
        if session_folder.exists():
            shutil.rmtree(session_folder)


def session_id_from_request(request: Request) -> str | None:
    value = request.headers.get(SESSION_HEADER) or request.query_params.get(SESSION_QUERY_PARAM)
    try:
        return normalize_session_id(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid RespiraScope session id") from exc


def session_manager_from_request(request: Request) -> SessionManager:
    return request.app.state.session_manager


def session_record_folder_for_request(request: Request) -> Path | None:
    session_id = session_id_from_request(request)
    if not session_id:
        return None
    return session_manager_from_request(request).record_folder(session_id)


def breath_system_for_request(request: Request) -> BreathProcessSystem:
    session_id = session_id_from_request(request)
    if session_id:
        return session_manager_from_request(request).get_system(session_id)

    from ct_breath.breath_process.breath_process_manager import breath_system

    return breath_system


def mock_controller_for_request(request: Request) -> MockBreathController:
    session_id = session_id_from_request(request)
    if session_id:
        return session_manager_from_request(request).get_mock_controller(session_id)
    return mock_breath_controller
