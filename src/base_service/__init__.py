import os
from importlib.metadata import version
from base_service.core.util.logging import instantiate_logger

__service_name__ = "BaseService"
__version__ = version("base-service")
__logging_level__ = os.getenv("LOGGING_LEVEL", "INFO")

instantiate_logger(__service_name__, __logging_level__)