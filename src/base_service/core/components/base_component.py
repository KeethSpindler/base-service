from abc import ABC, abstractmethod

from base_service.core.util.health import HealthCheckResult, HealthStatus


class BaseComponent(ABC):
    """Interface for asynchronously managed service components."""

    readiness_required = True

    @abstractmethod
    async def initialize(self) -> None:
        """Perform one-time component setup."""

    async def run(self) -> None:
        """Run the component when it owns a long-running task."""

    async def stop(self) -> None:
        """Release resources acquired during the component lifecycle."""

    async def health(self) -> HealthCheckResult:
        """Return the default healthy state for a running component."""
        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            component=type(self).__name__,
        )
