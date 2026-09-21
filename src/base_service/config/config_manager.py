"""Module for managing component-level configurations."""

class FastAPIConfig: ...

class ConfigManager:
    """Manager for component-level configurations."""

    def __init__(
        self,
        fastapi_config: FastAPIConfig = None,
    ):
        self.fastapi_config = fastapi_config or FastAPIConfig()



class FastAPIConfig:
    """Configuration for the FastAPI component."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self.host = host
        self.port = port
        self.debug = False
        self.reload = False