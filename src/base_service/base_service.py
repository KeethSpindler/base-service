"""Base Service Builder and instance classes for application scaffolding."""

import asyncio
from typing import Self

from base_service.core.components.base_component import BaseComponent
from base_service.core.components.fastapi_component import (
    FastAPIComponent,
    FastAPIConfig,
)
from base_service.core.enums.component_registry import ComponentRegistry


class BaseServiceBuilder:
    """Base Service Builder"""

    def __init__(self):
        self._service: "BaseService" = BaseService()

    def with_fastapi(self, config: FastAPIConfig | None = None) -> Self:
        """Add a FastAPI component configured with the supplied config."""
        self._service.set_fastapi_component(
            FastAPIComponent(config=config)
        )
        return self

    def build(self) -> "BaseService":
        """Build the service instance"""
        return self._service


class BaseService:
    """Base Service"""

    def __init__(self):
        self._components: dict[ComponentRegistry, BaseComponent] = {}

    def set_fastapi_component(self, component: FastAPIComponent) -> None:
        """Set the FastAPI component for the service"""
        self._components[ComponentRegistry.FASTAPI] = component
        return self

    def get_component(self, registry_key: ComponentRegistry) -> BaseComponent | None:
        """Retrieve a component by its registry key."""
        return self._components.get(registry_key)

    async def bootstrap(self) -> None:
        """Bootstrap the service after all components have been initialized.

        Override this method to perform any asynchronous setup required
        before the service starts running its components.
        """
        pass


    async def _run_services(self) -> None:
        """Initialize components, run the startup hook, then run each component."""
        for component in self._components.values():
            component.initialize()

        await self.bootstrap()
        await asyncio.gather(
            *(
                component.run()
                for component in self._components.values()
                if type(component).run is not BaseComponent.run
            )
        )

    async def shutdown(self) -> None:
        """Stop all running components."""
        await asyncio.gather(
            *(
                component.stop()
                for component in self._components.values()
                if type(component).stop is not BaseComponent.stop
            )
        )

    async def _run_with_shutdown(self) -> None:
        """Run the service and always attempt graceful shutdown on the same event loop."""
        try:
            await self._run_services()
        finally:
            await self.shutdown()

    def run(self) -> None:
        """Blocking entry point. Owns the event loop and runs all components."""
        asyncio.run(self._run_with_shutdown())
