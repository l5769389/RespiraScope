from fastapi import Body, FastAPI, HTTPException

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


def success_response(data=None, message: str = "ok", **extra):
    response = {
        "code": 1,
        "status": "success",
        "message": message,
        "data": data if data is not None else {},
    }
    response.update(extra)
    return response


def strip_scan_indexes(points):
    cleaned = []
    for point in points or []:
        if isinstance(point, dict):
            item = dict(point)
            item.pop("scan_indexes", None)
            cleaned.append(item)
        else:
            cleaned.append(point)
    return cleaned


def record_http_error(exc: ValueError, breath_system):
    return HTTPException(
        status_code=400,
        detail={
            "code": 0,
            "status": "error",
            "message": str(exc),
            "data": {"record": breath_system.status()["record"]},
        },
    )


def create_routes(app: FastAPI, app_config: AppConfig | None = None):
    config = app_config or get_config()
    register_core_routes(app, config)

    if config.enable_mock_signal:
        register_mock_routes(app)


def register_core_routes(app: FastAPI, app_config: AppConfig):
    @app.get("/")
    async def root():
        data = {
            "message": "IoT Breath Process Server is running",
            "mock_signal_enabled": app_config.enable_mock_signal,
            "front_console_enabled": app_config.console_enabled,
            "front_lab_enabled": app_config.lab_enabled,
            "front_monitor_enabled": app_config.monitor_enabled,
            "front_guide_enabled": app_config.console_enabled,
            "front_api_docs_enabled": app_config.console_enabled,
        }
        return success_response(data, **{key: value for key, value in data.items() if key != "message"})

    @app.get("/health")
    async def health_check():
        data = {
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
        return success_response(data, message="healthy", **{key: value for key, value in data.items() if key != "status"})

    @app.get("/runtime/config")
    async def runtime_config():
        data = {
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
        return success_response(data, **data)

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
        already_started = breath_system.is_start and breath_system.state == "running"
        stream = breath_system.start(config)
        stream = stream or breath_system.status()
        data = {
            "config": stream.get("filter_config", config.model_dump()),
            "stream": stream,
        }
        return success_response(
            data,
            message="Receive already started" if already_started else "Filter configuration updated",
            config=data["config"],
            stream=data["stream"],
        )

    @app.post("/stopReceive")
    async def stop_receive():
        from ct_breath.breath_process.breath_process_manager import breath_system

        await breath_system.stop()
        return success_response(
            {"stream": breath_system.status()},
            message="Receive stopped",
            stream=breath_system.status(),
        )

    @app.post("/setRTFilterParams")
    async def set_filter(config: FilterConfig | None = Body(default=None)):
        from ct_breath.breath_process.breath_process_manager import breath_system

        config = normalize_filter_config(config or FilterConfig())
        breath_system.update_filter_config(config)
        return success_response(
            {"config": config.model_dump()},
            message="Filter configuration updated",
            config=config.model_dump(),
        )

    @app.post("/record/start")
    async def start_record_breath():
        from ct_breath.breath_process.breath_process_manager import breath_system

        already_recording = breath_system.record_manager.recording
        try:
            record = breath_system.start_record()
        except ValueError as exc:
            raise record_http_error(exc, breath_system) from exc
        record = record or breath_system.status()["record"]
        return success_response(
            {"record": record},
            message="Record already started" if already_recording else "Record started",
            record=record,
        )

    @app.post("/record/end")
    async def end_record_breath():
        from ct_breath.breath_process.breath_process_manager import breath_system

        try:
            record = await breath_system.stop_record_and_filter()
        except ValueError as exc:
            raise record_http_error(exc, breath_system) from exc
        return success_response(
            strip_scan_indexes(record.get("filtered_data", [])),
            message="Record ended and offline filter completed",
            raw_data=strip_scan_indexes(record.get("raw_data", [])),
            peak=strip_scan_indexes(record.get("peak", [])),
            valley=strip_scan_indexes(record.get("valley", [])),
            metrics=record.get("metrics"),
            filter_status=record.get("filter_status"),
            segments=record.get("segments", {}),
            scans=record.get("scans", []),
            record_start_sequence=record.get("record_start_sequence"),
            record_end_sequence=record.get("record_end_sequence"),
            record_time=record.get("record_time", {}),
            record_padding=record.get("record_padding", {}),
        )

    @app.post("/record/reset")
    async def reset_record_breath():
        from ct_breath.breath_process.breath_process_manager import breath_system

        record = breath_system.reset_record()
        return success_response(
            {"record": record},
            message="Record reset",
            record=record,
        )

    @app.post("/scan/start")
    async def start_scan():
        from ct_breath.breath_process.breath_process_manager import breath_system

        try:
            scan = breath_system.start_scan()
        except ValueError as exc:
            raise record_http_error(exc, breath_system) from exc
        return success_response(
            {"scan": scan, "record": breath_system.status()["record"]},
            message="Scan started",
            scan=scan,
            record=breath_system.status()["record"],
        )

    @app.post("/scan/end")
    async def end_scan():
        from ct_breath.breath_process.breath_process_manager import breath_system

        try:
            scan = breath_system.stop_scan()
        except ValueError as exc:
            raise record_http_error(exc, breath_system) from exc
        return success_response(
            {"scan": scan, "record": breath_system.status()["record"]},
            message="Scan ended",
            scan=scan,
            record=breath_system.status()["record"],
        )

    @app.post("/record/save")
    async def save_record_to_file(config: SaveBreathConfig | None = Body(default=None)):
        from ct_breath.breath_process.breath_process_manager import breath_system

        config = config or SaveBreathConfig()
        try:
            file_path = await breath_system.save_record(config.folder_path)
        except ValueError as exc:
            raise record_http_error(exc, breath_system) from exc
        return success_response({"file_path": file_path})

    @app.post("/applyFilter")
    async def apply_filter(config: ApplyFilterConfig | None = Body(default=None)):
        from ct_breath.breath_process.breath_process_manager import breath_system

        config = config or ApplyFilterConfig()
        config.filter_config = normalize_filter_config(config.filter_config)
        filter_data, peak, valley, filter_config, metrics = await breath_system.apply_filter(config)
        return success_response(
            filter_data,
            peak=peak,
            valley=valley,
            filter_config=filter_config,
            metrics=metrics,
        )


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
