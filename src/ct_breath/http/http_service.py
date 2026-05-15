from fastapi import Body, FastAPI

from ct_breath.config import AppConfig, get_config
from ct_breath.http.schemas import (
    ApplyFilterConfig,
    FilterConfig,
    MockBreathConfigRequest,
    MockBreathPreviewRequest,
    SaveBreathConfig,
    StreamStatusResponse,
    normalize_filter_config,
)
from ct_breath.mock_sensor.breath_simulator import (
    MockBreathConfig,
    SCENARIO_PRESETS,
    config_to_dict,
    generate_preview,
    mock_breath_controller,
)


def build_preview_config(payload: dict) -> MockBreathConfig:
    scenario = payload.get("scenario") or mock_breath_controller.get_config().scenario
    base = config_to_dict(SCENARIO_PRESETS.get(scenario, mock_breath_controller.get_config()))
    base.update({key: value for key, value in payload.items() if value is not None})
    return MockBreathConfig(**base)


def create_routes(app: FastAPI, app_config: AppConfig | None = None):
    config = app_config or get_config()
    register_core_routes(app, config)

    if config.enable_mock_signal:
        register_mock_routes(app)


def register_core_routes(app: FastAPI, app_config: AppConfig):
    @app.get("/")
    async def root():
        return {
            "message": "IoT Breath Process Server is running",
            "mock_signal_enabled": app_config.enable_mock_signal,
            "front_console_enabled": app_config.console_enabled,
            "front_lab_enabled": app_config.lab_enabled,
            "front_monitor_enabled": app_config.monitor_enabled,
            "front_guide_enabled": app_config.console_enabled,
            "front_api_docs_enabled": app_config.console_enabled,
        }

    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "mock_signal_enabled": app_config.enable_mock_signal,
            "sensor": {
                "host": app_config.sensor_host,
                "port": app_config.sensor_port,
            },
            "frontends": {
                "console_enabled": app_config.console_enabled,
                "console_host": app_config.console_host,
                "console_port": app_config.console_port if app_config.console_enabled else None,
                "lab_enabled": app_config.lab_enabled,
                "monitor_enabled": app_config.monitor_enabled,
                "guide_enabled": app_config.console_enabled,
                "api_docs_enabled": app_config.console_enabled,
            },
        }

    @app.get("/runtime/config")
    async def runtime_config():
        return {
            "mock_signal_enabled": app_config.enable_mock_signal,
            "config_path": str(app_config.config_path),
            "sensor": {
                "host": app_config.sensor_host,
                "port": app_config.sensor_port,
            },
            "backend_host": app_config.backend_host,
            "backend_port": app_config.backend_port,
            "console_enabled": app_config.console_enabled,
            "console_host": app_config.console_host,
            "console_port": app_config.console_port if app_config.console_enabled else None,
            "guide_enabled": app_config.console_enabled,
            "guide_host": app_config.console_host,
            "guide_port": app_config.console_port if app_config.console_enabled else None,
            "api_docs_enabled": app_config.console_enabled,
            "api_docs_host": app_config.console_host,
            "api_docs_port": app_config.console_port if app_config.console_enabled else None,
            "lab_enabled": app_config.lab_enabled,
            "lab_host": app_config.console_host,
            "lab_port": app_config.console_port if app_config.console_enabled and app_config.lab_enabled else None,
            "monitor_enabled": app_config.monitor_enabled,
            "monitor_host": app_config.console_host,
            "monitor_port": app_config.console_port if app_config.console_enabled and app_config.monitor_enabled else None,
            "record": {
                "pre_points": app_config.record_pre_points,
                "post_points": app_config.record_post_points,
            },
        }

    @app.get("/stream/status", response_model=StreamStatusResponse)
    async def stream_status():
        from ct_breath.breath_process.breath_process_manager import breath_system

        return StreamStatusResponse(
            code=1,
            status="success",
            data=breath_system.status(),
        )

    @app.post("/startReceive")
    async def start_receive(config: FilterConfig | None = Body(default=None)):
        from ct_breath.breath_process.breath_process_manager import breath_system

        config = normalize_filter_config(config or FilterConfig())
        breath_system.start(config)
        return {
            "status": "success",
            "message": "Filter configuration updated",
            "config": config.model_dump(),
            "stream": breath_system.status(),
        }

    @app.post("/setRTFilterParams")
    async def set_filter(config: FilterConfig | None = Body(default=None)):
        from ct_breath.breath_process.breath_process_manager import breath_system

        config = normalize_filter_config(config or FilterConfig())
        breath_system.update_filter_config(config)
        return {
            "status": "success",
            "message": "Filter configuration updated",
            "config": config.model_dump(),
        }

    @app.post("/record/start")
    async def start_record_breath():
        from ct_breath.breath_process.breath_process_manager import breath_system

        breath_system.start_record()
        return {
            "status": "success",
            "message": "ok",
        }

    @app.post("/record/end")
    async def end_record_breath():
        from ct_breath.breath_process.breath_process_manager import breath_system

        breath_system.stop_record()
        return {
            "status": "success",
            "message": "ok",
        }

    @app.post("/record/save")
    async def save_record_to_file(config: SaveBreathConfig | None = Body(default=None)):
        from ct_breath.breath_process.breath_process_manager import breath_system

        config = config or SaveBreathConfig()
        file_path = await breath_system.save_record(config.folder_path)
        return {
            "code": 1,
            "status": "success",
            "message": "ok",
            "data": {
                "file_path": file_path,
            },
        }

    @app.post("/applyFilter")
    async def apply_filter(config: ApplyFilterConfig | None = Body(default=None)):
        from ct_breath.breath_process.breath_process_manager import breath_system

        config = config or ApplyFilterConfig()
        config.filter_config = normalize_filter_config(config.filter_config)
        filter_data, peak, valley, filter_config, metrics = await breath_system.apply_filter(config)
        return {
            "code": 1,
            "status": "success",
            "message": "ok",
            "data": filter_data,
            "peak": peak,
            "valley": valley,
            "filter_config": filter_config,
            "metrics": metrics,
        }


def register_mock_routes(app: FastAPI):
    @app.get("/mock/scenarios")
    async def mock_scenarios():
        return {
            "code": 1,
            "data": mock_breath_controller.list_scenarios(),
        }

    @app.get("/mock/config")
    async def mock_config():
        return {
            "code": 1,
            "data": config_to_dict(mock_breath_controller.get_config()),
        }

    @app.post("/mock/config")
    async def set_mock_config(config: MockBreathConfigRequest):
        next_config = mock_breath_controller.set_config(config.model_dump(exclude_none=True))
        return {
            "code": 1,
            "data": config_to_dict(next_config),
        }

    @app.post("/mock/preview")
    async def mock_preview(config: MockBreathPreviewRequest):
        payload = config.model_dump(exclude_none=True)
        seconds = payload.pop("seconds")
        sampling_rate = payload.pop("sampling_rate")
        preview_config = build_preview_config(payload)
        return {
            "code": 1,
            "data": generate_preview(preview_config, seconds, sampling_rate),
            "config": config_to_dict(preview_config),
            "sampling_rate": sampling_rate,
        }
