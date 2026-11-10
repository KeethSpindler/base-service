"""FastAPI component implementation for service composition."""

from logging import getLogger
from os import getenv
from typing import Any, Callable

from fastapi import APIRouter as ApiRouter
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import uvicorn

from base_service.core.components.base_component import BaseComponent
from base_service import __service_name__, __version__

logger = getLogger(f"{__service_name__}.FastAPIComponent")


class FastAPIConfig:
    """Configuration for the FastAPI component."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self.title = "FastAPI Application"
        self.description = "FastAPI Application"
        self.version = __version__
        self.host = getenv("FASTAPI_HOST", host)
        self.port = int(getenv("FASTAPI_PORT", port))
        self.debug = getenv("FASTAPI_DEBUG", "False").lower() in ("true", "1", "yes")
        self.reload = getenv("FASTAPI_RELOAD", "False").lower() in ("true", "1", "yes")
        self.cors = getenv("FASTAPI_CORS", "*").split(",")


class FastAPIComponent(BaseComponent):
    """Component that owns FastAPI app creation and ASGI server lifecycle."""

    def __init__(
        self, config: FastAPIConfig | None = None, app: FastAPI | None = None
    ):
        self._config = config if config is not None else FastAPIConfig()
        self._server: uvicorn.Server | None = None
        self.app: FastAPI = app if app is not None else self._get_app(self._config)

    def initialize(self) -> None:
        """The app is configured during construction; no additional setup is needed."""

    def _get_app(self, config: FastAPIConfig) -> FastAPI:
        """Create and return a FastAPI app instance."""
        app = FastAPI(
            title=config.title,
            description=config.description,
            version=config.version,
            debug=config.debug,
        )
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["*"],
        )
        return app

    def attach_lifespan(self, lifespan: Callable[..., Any]) -> None:
        """Attach a lifespan context manager to the FastAPI app."""
        if not callable(lifespan):
            raise ValueError("Lifespan must be a viable callable")

        self.app.router.lifespan_context = lifespan

    def add_api_router(self, router: ApiRouter) -> None:
        """Add an API router to the FastAPI app."""
        if not isinstance(router, ApiRouter):
            raise ValueError("router must be an instance of APIRouter")

        self.app.include_router(router)

    async def run(self) -> None:
        """Start the ASGI server and block until it stops."""
        uvicorn_config = uvicorn.Config(
            app=self.app,
            host=self._config.host,
            port=self._config.port,
            reload=self._config.reload,
        )

        self._server = uvicorn.Server(uvicorn_config)

        logger.info("Starting FastAPI ASGI server...")
        try:
            await self._server.serve()
        finally:
            logger.info("FastAPI ASGI server has stopped.")

    async def stop(self) -> None:
        """Request graceful server shutdown."""
        if self._server is not None:
            logger.info("Stopping FastAPI ASGI server...")
            self._server.should_exit = True
            logger.info("FastAPI ASGI server shutdown requested.")

        