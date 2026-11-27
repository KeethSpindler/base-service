"""Base Service Builder and instance classes for application scaffolding."""

import asyncio
from collections.abc import Hashable
from enum import StrEnum
from typing import Self

from base_service.core.components.base_component import BaseComponent
from base_service.core.components.fastapi_component import (
    FastAPIComponent,
    FastAPIConfig,
)
from base_service.core.enums.component_registry import ComponentRegistry


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

    def __init__(self, service: "BaseService | None" = None) -> None:
        self._service = service if service is not None else BaseService()

    def with_fastapi(self, config: FastAPIConfig | None = None) -> Self:
        """Add a FastAPI component configured with the supplied config."""
        self._service.set_fastapi_component(FastAPIComponent(config=config))
        return self

    def build(self) -> "BaseService":
        """Build the service instance."""
        return self._service


class BaseService:
    """Lifecycle container for asynchronous service components."""

    def __init__(self) -> None:
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
                await component.initialize()

            self._state = LifecycleState.STARTING
            await self.bootstrap()

            self._state = LifecycleState.RUNNING
            tasks = [
                asyncio.create_task(component.run())
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

    async def shutdown(self) -> None:
        """Stop attempted components in reverse registration order."""
        async with self._shutdown_lock:
            if self._shutdown_complete:
                return

            self._state = LifecycleState.STOPPING
            errors: list[BaseException] = []
            cancellation: asyncio.CancelledError | None = None
            for component in reversed(self._initialization_attempted):
                stop_task = asyncio.create_task(component.stop())
                try:
                    await asyncio.shield(stop_task)
                except asyncio.CancelledError as exc:
                    if stop_task.done():
                        errors.append(exc)
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
                except (
                    Exception,
                    KeyboardInterrupt,
                    SystemExit,
                    GeneratorExit,
                ) as exc:
                    errors.append(exc)
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
