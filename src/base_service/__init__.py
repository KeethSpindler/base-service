from importlib.metadata import version

from base_service.core.util.logging import instantiate_logger
from base_service.core.util.health import (
    HealthChecker,
    HealthCheckResult,
    HealthStatus,
    ServiceHealthResult,
)
from base_service.config.settings import ServiceSettings

__service_name__ = "BaseService"
__version__ = version("base-service")

instantiate_logger(__service_name__, "INFO")

__all__ = [
    "HealthChecker",
    "HealthCheckResult",
    "HealthStatus",
    "ServiceHealthResult",
    "ServiceSettings",
]