# base-service

Foundation library for building component-driven microservices. Provides a `BaseService` container and `BaseComponent` interface intended to be inherited and extended — not run directly.

## Concepts

### `BaseService`

The service container. Manages the lifecycle of all registered components:

1. **Initialize** — calls `initialize()` on every component.
2. **Startup** — runs the overridable `startup()` hook for any pre-run service logic.
3. **Run** — concurrently gathers `run()` coroutines for all components that override it.
4. **Shutdown** — concurrently gathers `stop()` coroutines for all components that override it.

Subclass `BaseService` to create a concrete service. Override `startup()` to inject logic that runs after components are initialized but before they start.

```python
class MyService(BaseService):
    async def startup(self) -> None:
        print("All components initialized, starting up...")
```

### `BaseComponent`

The interface every component must implement. Subclass it and provide at minimum an `initialize()` method.

| Method | Required | Purpose |
|---|---|---|
| `initialize()` | Yes | One-time setup (config loading, client creation, etc.) |
| `run()` | No | Long-running async loop. Only called if overridden. |
| `stop()` | No | Graceful teardown. Only called if overridden. |

Components that don't override `run()` or `stop()` are treated as utility components and are skipped during the gather phases.

```python
class MyComponent(BaseComponent):
    def initialize(self):
        self._client = create_client()

    async def run(self) -> None:
        while True:
            await self._client.poll()

    async def stop(self) -> None:
        await self._client.close()
```

### `ComponentRegistry`

A `StrEnum` used as the key when registering components with a service. Extend it to define the registry keys for your service.

```python
from enum import auto
from base_service.core.enums.component_registry import ComponentRegistry

class MyRegistry(ComponentRegistry):
    DATABASE = auto()
    MESSAGE_BUS = auto()
```

### `BaseServiceBuilder`

Fluent builder for assembling a service before starting it.

```python
service = (
    BaseServiceBuilder()
    .with_component(DatabaseComponent(), MyRegistry.DATABASE)
    .with_component(MessageBusComponent(), MyRegistry.MESSAGE_BUS)
    .build()
)

service.start()
```

## Installation

Requires Python 3.13+.

```bash
pip install -e .
```

## Development

```bash
pip install -e ".[dev]"
pytest
```
