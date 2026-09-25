"""Module for managing component-level configurations."""

from base_service import __version__
from os import getenv

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

class ConfigManager:
    """Manager for component-level configurations."""

    def __init__(
        self,
        fastapi_config: FastAPIConfig = None,
    ):
        self.fastapi_config = fastapi_config or FastAPIConfig()
