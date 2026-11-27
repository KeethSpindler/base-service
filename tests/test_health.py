import asyncio

import pytest

from base_service.base_service import BaseService
from base_service.core.components.base_component import BaseComponent
from base_service.core.util.health import HealthCheckResult, HealthStatus
from base_service.config.settings import ServiceSettings


class HealthComponent(BaseComponent):
    def __init__(
        self,
        name: str,
        check_result: HealthCheckResult,
        *,
        required: bool = True,
        error: BaseException | None = None,
        delay: float = 0,
    ) -> None:
        self.name = name
        self.result = check_result
        self.readiness_required = required
        self.error = error
        self.delay = delay

    async def initialize(self) -> None:
        pass

    async def health(self) -> HealthCheckResult:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.result


class InspectableHealthService(BaseService):
    def __init__(
        self,
        *components: BaseComponent,
        timeout: float = 0.01,
    ) -> None:
        super().__init__(
            ServiceSettings(
                service_name="health-service",
                health_check_timeout_seconds=timeout,
            )
        )
        self._components.update(
            (f"component:{index}", component)
            for index, component in enumerate(components)
        )


def health_result(
    component: str,
    status: HealthStatus,
    message: str | None = None,
) -> HealthCheckResult:
    return HealthCheckResult(
        component=component,
        status=status,
        message=message,
    )


def test_default_component_health_is_healthy() -> None:
    class UtilityComponent(BaseComponent):
        async def initialize(self) -> None:
            pass

    check = asyncio.run(UtilityComponent().health())

    assert check == HealthCheckResult(
        component="UtilityComponent",
        status=HealthStatus.HEALTHY,
    )


def test_liveness_only_checks_event_loop_continuity() -> None:
    service = InspectableHealthService(
        HealthComponent(
            "not-checked",
            health_result("not-checked", HealthStatus.UNHEALTHY),
            error=RuntimeError("must not be called"),
        )
    )

    check = asyncio.run(service.liveness())

    assert check.component == "health-service"
    assert check.status is HealthStatus.HEALTHY


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([HealthStatus.HEALTHY], HealthStatus.HEALTHY),
        (
            [HealthStatus.HEALTHY, HealthStatus.DEGRADED],
            HealthStatus.DEGRADED,
        ),
        (
            [HealthStatus.DEGRADED, HealthStatus.UNHEALTHY],
            HealthStatus.UNHEALTHY,
        ),
    ],
)
def test_readiness_aggregates_required_component_statuses(
    statuses: list[HealthStatus],
    expected: HealthStatus,
) -> None:
    components = [
        HealthComponent(
            f"component-{index}",
            health_result(f"component-{index}", status),
        )
        for index, status in enumerate(statuses)
    ]
    service = InspectableHealthService(*components)

    report = asyncio.run(service.readiness())

    assert report.status is expected
    assert len(report.checks) == len(statuses)


@pytest.mark.parametrize(
    "optional_status",
    [HealthStatus.DEGRADED, HealthStatus.UNHEALTHY],
)
def test_optional_component_does_not_fail_readiness(
    optional_status: HealthStatus,
) -> None:
    service = InspectableHealthService(
        HealthComponent(
            "required",
            health_result("required", HealthStatus.HEALTHY),
        ),
        HealthComponent(
            "optional",
            health_result("optional", optional_status),
            required=False,
        ),
    )

    report = asyncio.run(service.readiness())

    assert report.status is HealthStatus.HEALTHY
    assert report.checks[1].status is optional_status


def test_health_timeout_is_unhealthy_without_blocking_other_checks() -> None:
    service = InspectableHealthService(
        HealthComponent(
            "timeout",
            health_result("timeout", HealthStatus.HEALTHY),
            delay=1,
        ),
        HealthComponent(
            "healthy",
            health_result("healthy", HealthStatus.HEALTHY),
        ),
        timeout=0.001,
    )

    report = asyncio.run(service.readiness())

    assert report.status is HealthStatus.UNHEALTHY
    assert report.checks[0].message == "health check timed out"
    assert report.checks[1].status is HealthStatus.HEALTHY


def test_health_failure_is_converted_to_unhealthy_result() -> None:
    service = InspectableHealthService(
        HealthComponent(
            "broken",
            health_result("broken", HealthStatus.HEALTHY),
            error=RuntimeError("secret failure detail"),
        )
    )

    report = asyncio.run(service.readiness())

    assert report.status is HealthStatus.UNHEALTHY
    assert report.checks[0].message == "health check failed: RuntimeError"
    assert "secret failure detail" not in report.checks[0].model_dump_json()


def test_invalid_health_result_is_reported_as_unhealthy() -> None:
    class InvalidHealthComponent(HealthComponent):
        async def health(self) -> HealthCheckResult:
            return "not-a-result"  # type: ignore[return-value]

    service = InspectableHealthService(
        InvalidHealthComponent(
            "invalid",
            health_result("invalid", HealthStatus.HEALTHY),
        )
    )

    report = asyncio.run(service.readiness())

    assert report.status is HealthStatus.UNHEALTHY
    assert report.checks[0].message == "health check failed: TypeError"


def test_cancelled_health_check_preserves_cancellation() -> None:
    class CancelledHealthComponent(HealthComponent):
        async def health(self) -> HealthCheckResult:
            raise asyncio.CancelledError

    service = InspectableHealthService(
        CancelledHealthComponent(
            "cancelled",
            health_result("cancelled", HealthStatus.HEALTHY),
        )
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(service.readiness())


def test_readiness_without_components_is_healthy() -> None:
    service = InspectableHealthService()

    report = asyncio.run(service.readiness())

    assert report.status is HealthStatus.HEALTHY
    assert report.checks == ()
