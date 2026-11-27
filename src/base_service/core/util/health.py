"""Health-check contracts and dependency status aggregation."""

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class HealthStatus(StrEnum):
    """Aggregate health state used by probes and components."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheckResult(BaseModel):
    """Result returned by a component health check."""

    status: HealthStatus
    component: str
    message: str | None = None


class ServiceHealthResult(HealthCheckResult):
    """Service-level result containing the underlying component checks."""

    checks: tuple[HealthCheckResult, ...] = ()


@runtime_checkable
class HealthChecker(Protocol):
    """Protocol implemented by components with health checks."""

    async def health(self) -> HealthCheckResult:
        """Return the current component health."""
