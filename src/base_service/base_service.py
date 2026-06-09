"""Base Service Builder and instance for Suvoda simulation services"""

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
        self, component: BaseComponent, registry_key: ComponentRegistry
    ) -> Self:
        """Register a component and return the builder for chaining."""
        self._service.add_component(component, registry_key)
        return self

    def build(self) -> "BaseService":
        """Build the service instance"""
        return self._service


class BaseService:
    """Base Service"""

    def __init__(self):
        self._components: dict[ComponentRegistry, BaseComponent] = {}

    def add_component(
        self, component: BaseComponent, registry_key: ComponentRegistry
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

    async def startup(self) -> None:
        """Override in subclasses to inject custom startup logic before components begin running."""
        pass

    async def run(self) -> None:
        """Initialize all components and gather their coroutines into a single event loop."""
        self.initialize_components()
        await self.startup()
        await asyncio.gather(
            *(c.run() for c in self._components.values() if type(c).run is not BaseComponent.run)
        )

    async def shutdown(self) -> None:
        """Stop all running components."""
        await asyncio.gather(
            *(c.stop() for c in self._components.values() if type(c).stop is not BaseComponent.stop)
        )

    def start(self) -> None:
        """Blocking entry point. Owns the event loop and runs all components."""
        if not inspect.iscoroutinefunction(self.run):
            raise TypeError(
                f"{type(self).__name__}.run() must be 'async def run()'. "
                "To inject custom startup logic, override 'startup()' instead of 'run()'."
            )
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            asyncio.run(self.shutdown())
            raise
        except Exception:
            asyncio.run(self.shutdown())
            raise
