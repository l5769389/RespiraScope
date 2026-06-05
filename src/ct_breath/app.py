import asyncio
from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ct_breath.breath_process.breath_process_manager import breath_system
from ct_breath.config import AppConfig, get_config
from ct_breath.http.http_service import create_routes
from ct_breath.logger import logger
from ct_breath.mock_sensor.async_sensor import async_sensor_start
from ct_breath.session import SessionManager
from ct_breath.socket_io_service import set_session_touch_callback, sio


def lifespan_for(app_config: AppConfig):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        tasks = []

        try:
            logger.info("Starting background tasks...")

            if app_config.enable_mock_signal:
                mock_sensor_task = asyncio.create_task(async_sensor_start(app_config))
                tasks.append(mock_sensor_task)
                logger.info("Mock signal server enabled")
            else:
                logger.info("Mock signal server disabled")

            socket_client_task = asyncio.create_task(breath_system.start_system())
            tasks.append(socket_client_task)

            cleanup_task = asyncio.create_task(app.state.session_manager.cleanup_idle_sessions())
            tasks.append(cleanup_task)
            set_session_touch_callback(app.state.session_manager.touch)

            logger.info("All background tasks started")
            yield

        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            raise

        finally:
            logger.info("Shutting down application...")
            set_session_touch_callback(None)
            await app.state.session_manager.stop_all()
            await breath_system.stop_system()

            for task in tasks:
                if not task.done():
                    task.cancel()

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for index, result in enumerate(results):
                    if isinstance(result, asyncio.CancelledError):
                        logger.info(f"Task {index} cancelled")
                    elif isinstance(result, Exception):
                        logger.error(f"Task {index} failed: {result}")
                    else:
                        logger.info(f"Task {index} completed")

    return lifespan


def create_app(app_config: AppConfig | None = None) -> FastAPI:
    config = app_config or get_config()
    app = FastAPI(
        title="IoT Breath Process Server",
        description="Real-time API service for processing breath sensor data",
        version="0.1.0",
        lifespan=lifespan_for(config),
    )
    app.state.config = config
    app.state.session_manager = SessionManager(config)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    create_routes(app, config)
    return app


def create_socket_app(app_config: AppConfig | None = None):
    return socketio.ASGIApp(sio, create_app(app_config))
