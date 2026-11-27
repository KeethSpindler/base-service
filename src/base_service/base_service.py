"""Base Service Builder and instance classes for application scaffolding."""

import asyncio
from collections.abc import Hashable
from enum import StrEnum
from typing import Self

from base_service.core.util.logging import configure_logging, get_component_logger
from base_service.core.components.base_component import BaseComponent
from base_service.core.components.fastapi_component import (
    FastAPIComponent,
    FastAPIConfig,
)
from base_service.core.enums.component_registry import ComponentRegistry
from base_service.core.util.health import (
    HealthCheckResult,
    HealthStatus,
    ServiceHealthResult,
)
from base_service.config.settings import ServiceSettings


class LifecycleState(StrEnum):
    """Current state of a service instance."""

    CREATED = "created"
    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class BaseServiceBuilder:
    """Fluent builder for a service and its bundled components."""

    def __init__(
        self,
        service: "BaseService | None" = None,
        *,
        settings: ServiceSettings | None = None,
    ) -> None:
        self._service = (
            service if service is not None else BaseService(settings=settings)
        )

    def with_fastapi(self, config: FastAPIConfig | None = None) -> Self:
        """Add a FastAPI component configured with the supplied config."""
        self._service.set_fastapi_component(FastAPIComponent(config=config))
        return self

    def build(self) -> "BaseService":
        """Build the service instance."""
        return self._service


class BaseService:
    """Lifecycle container for asynchronous service components."""

    def __init__(self, settings: ServiceSettings | None = None) -> None:
        self.settings = settings or ServiceSettings(service_name="BaseService")
        configure_logging(self.settings)
        self._logger = get_component_logger(
            self.settings.service_name,
            type(self).__name__,
        )
        self._components: dict[Hashable, BaseComponent] = {}
        self._initialization_attempted: list[BaseComponent] = []
        self._state = LifecycleState.CREATED
        self._shutdown_complete = False
        self._shutdown_lock = asyncio.Lock()

    @property
    def state(self) -> LifecycleState:
        """Return the current lifecycle state."""
        return self._state

    def set_fastapi_component(self, component: FastAPIComponent) -> Self:
        """Register the FastAPI component for the service."""
        if not isinstance(component, FastAPIComponent):
            raise TypeError("component must be a FastAPIComponent")
        if self._state is not LifecycleState.CREATED:
            raise RuntimeError(
                f"cannot register components while service is {self._state}"
            )
        if ComponentRegistry.FASTAPI in self._components:
            raise ValueError("FastAPI component already exists")

        self._components[ComponentRegistry.FASTAPI] = component
        return self

    def get_component(
        self, registry_key: ComponentRegistry
    ) -> BaseComponent | None:
        """Retrieve a component by its registry key."""
        return self._components.get(registry_key)

    async def liveness(self) -> HealthCheckResult:
        """Verify that the event loop can continue processing work."""
        await asyncio.sleep(0)
        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            component=self.settings.service_name,
            message="event loop is responsive",
        )

    async def readiness(self) -> ServiceHealthResult:
        """Aggregate bounded health checks for registered components."""
        component_checks = await asyncio.gather(
            *(
                self._check_component_health(component)
                for component in self._components.values()
            )
        )
        required_statuses = [
            result.status
            for component, result in zip(
                self._components.values(),
                component_checks,
                strict=True,
            )
            if component.readiness_required
        ]

        if HealthStatus.UNHEALTHY in required_statuses:
            status = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in required_statuses:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        return ServiceHealthResult(
            status=status,
            component=self.settings.service_name,
            checks=tuple(component_checks),
        )

    async def _check_component_health(
        self,
        component: BaseComponent,
    ) -> HealthCheckResult:
        component_name = type(component).__name__
        try:
            result = await asyncio.wait_for(
                component.health(),
                timeout=self.settings.health_check_timeout_seconds,
            )
            if not isinstance(result, HealthCheckResult):
                raise TypeError(
                    "health() must return a HealthCheckResult"
                )
            return result
        except asyncio.TimeoutError:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component=component_name,
                message="health check timed out",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component=component_name,
                message=f"health check failed: {type(exc).__name__}",
            )

    async def bootstrap(self) -> None:
        """Run service-specific setup after components initialize."""

    async def _run(self) -> None:
        """Own initialization, bootstrap, component tasks, and cleanup."""
        if self._state is not LifecycleState.CREATED:
            raise RuntimeError(f"service cannot start while {self._state}")

        tasks: list[asyncio.Task[None]] = []
        try:
            self._state = LifecycleState.INITIALIZING
            for component in self._components.values():
                self._initialization_attempted.append(component)
                logger = get_component_logger(
                    self.settings.service_name,
                    type(component).__name__,
                )
                logger.info(
                    "Initializing component",
                    extra={
                        "event": "component.initialize",
                        "action": "initialize",
                        "lifecycle_state": self._state,
                    },
                )
                await component.initialize()

            self._state = LifecycleState.STARTING
            await self.bootstrap()

            self._state = LifecycleState.RUNNING
            tasks = [
                asyncio.create_task(self._run_component(component))
                for component in self._components.values()
            ]
            await asyncio.gather(*tasks)
        except (
            Exception,
            asyncio.CancelledError,
            KeyboardInterrupt,
            SystemExit,
            GeneratorExit,
        ) as run_error:
            self._state = LifecycleState.FAILED
            self._logger.exception(
                "Service lifecycle failed",
                extra={
                    "event": "service.failure",
                    "action": "run",
                    "lifecycle_state": self._state,
                },
            )
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            try:
                await self.shutdown()
            except (
                Exception,
                asyncio.CancelledError,
                KeyboardInterrupt,
                SystemExit,
                GeneratorExit,
            ) as shutdown_error:
                raise BaseExceptionGroup(
                    "service failed during run and shutdown",
                    [run_error, shutdown_error],
                ) from run_error
            raise
        else:
            await self.shutdown()

    async def _run_component(self, component: BaseComponent) -> None:
        logger = get_component_logger(
            self.settings.service_name,
            type(component).__name__,
        )
        logger.info(
            "Running component",
            extra={
                "event": "component.run",
                "action": "run",
                "lifecycle_state": self._state,
            },
        )
        try:
            await component.run()
        except asyncio.CancelledError:
            logger.info(
                "Component run cancelled",
                extra={
                    "event": "component.cancelled",
                    "action": "run",
                    "lifecycle_state": LifecycleState.STOPPING,
                },
            )
            raise
        except BaseException:
            logger.exception(
                "Component run failed",
                extra={
                    "event": "component.failure",
                    "action": "run",
                    "lifecycle_state": LifecycleState.FAILED,
                },
            )
            raise

    async def shutdown(self) -> None:
        """Stop attempted components in reverse registration order."""
        async with self._shutdown_lock:
            if self._shutdown_complete:
                return

            self._state = LifecycleState.STOPPING
            errors: list[BaseException] = []
            cancellation: asyncio.CancelledError | None = None
            for component in reversed(self._initialization_attempted):
                logger = get_component_logger(
                    self.settings.service_name,
                    type(component).__name__,
                )
                logger.info(
                    "Stopping component",
                    extra={
                        "event": "component.stop",
                        "action": "stop",
                        "lifecycle_state": self._state,
                    },
                )
                stop_task = asyncio.create_task(component.stop())
                try:
                    await asyncio.shield(stop_task)
                except asyncio.CancelledError as exc:
                    if stop_task.done():
                        errors.append(exc)
                        logger.exception(
                            "Component stop was cancelled",
                            extra={
                                "event": "component.stop_cancelled",
                                "action": "stop",
                                "lifecycle_state": LifecycleState.FAILED,
                            },
                        )
                    else:
                        cancellation = exc
                        try:
                            await stop_task
                        except (
                            Exception,
                            asyncio.CancelledError,
                            KeyboardInterrupt,
                            SystemExit,
                            GeneratorExit,
                        ) as stop_error:
                            errors.append(stop_error)
                            logger.exception(
                                "Component stop failed during cancellation",
                                extra={
                                    "event": "component.stop_failure",
                                    "action": "stop",
                                    "lifecycle_state": LifecycleState.FAILED,
                                },
                            )
                except (
                    Exception,
                    KeyboardInterrupt,
                    SystemExit,
                    GeneratorExit,
                ) as exc:
                    errors.append(exc)
                    logger.exception(
                        "Component stop failed",
                        extra={
                            "event": "component.stop_failure",
                            "action": "stop",
                            "lifecycle_state": LifecycleState.FAILED,
                        },
                    )
            self._shutdown_complete = True

            if errors:
                if cancellation is not None:
                    errors.insert(0, cancellation)
                self._state = LifecycleState.FAILED
                if len(errors) == 1:
                    raise errors[0]
                raise BaseExceptionGroup(
                    "multiple component shutdown failures",
                    errors,
                )

            self._state = LifecycleState.STOPPED
            if cancellation is not None:
                raise cancellation

    def run(self) -> None:
        """Blocking entry point. Owns the event loop and runs all components."""
        asyncio.run(self._run())
