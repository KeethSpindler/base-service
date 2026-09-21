"""Base Service Builder and instance classes for application scaffolding."""

import asyncio
import inspect
from typing import Self
from base_service.core.enums.component_registry import ComponentRegistry
from base_service.core.components.base_component import BaseComponent

class BaseServiceBuilder:
    """Base Service Builder"""

    def __init__(self):
        self._service: "BaseService" = BaseService()

    def with_component(
        self, registry_key: ComponentRegistry, component: BaseComponent
    ) -> Self:
        """Register a component and return the builder for chaining."""
        self._service.add_component(registry_key, component)
        return self

    def build(self) -> "BaseService":
        """Build the service instance"""
        return self._service


class BaseService:
    """Base Service"""

    def __init__(self):
        self._components: dict[ComponentRegistry, BaseComponent] = {}

    def add_component(
        self, registry_key: ComponentRegistry, component: BaseComponent
    ) -> None:
        """Add a component to the service"""
        if registry_key in self._components:
            raise ValueError(
                f"Component with registry key {registry_key} already exists"
            )

        self._components[registry_key] = component

    def initialize_components(self) -> None:
        """Initialize all components"""
        for component in self._components.values():
            component.initialize()

    async def bootstrap(self) -> None:
        """Override in subclasses to inject custom bootstrap logic before components begin running."""
        pass

    async def run(self) -> None:
        """Initialize all components and gather their coroutines into a single event loop."""
        self.initialize_components()
        await self.bootstrap()
        await asyncio.gather(
            *(c.run() for c in self._components.values() if type(c).run is not BaseComponent.run)
        )

    async def shutdown(self) -> None:
        """Stop all running components."""
        await asyncio.gather(
            *(c.stop() for c in self._components.values() if type(c).stop is not BaseComponent.stop)
        )

    async def _run_with_shutdown(self) -> None:
        """Run the service and always attempt graceful shutdown on the same event loop."""
        try:
            await self.run()
        except BaseException:
            try:
                await self.shutdown()
            except Exception:
                # Preserve the original failure from run().
                pass
            raise
        else:
            await self.shutdown()

    def start(self) -> None:
        """Blocking entry point. Owns the event loop and runs all components."""
        if not inspect.iscoroutinefunction(self.run):
            raise TypeError(
                f"{type(self).__name__}.run() must be 'async def run()'. "
                "To inject custom bootstrap logic, override 'bootstrap()' instead of 'run()'."
            )
        asyncio.run(self._run_with_shutdown())
