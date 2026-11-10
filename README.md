# base-service

Foundation library for building component-driven microservices. Provides a `BaseService` container, a fluent builder, and reusable components.

## Concepts

### `BaseService`

The service container. Manages the lifecycle of all registered components:

1. **Initialize** — calls `initialize()` on every component.
2. **Startup** — runs the overridable `startup()` hook for any pre-run service logic. The legacy `bootstrap()` hook delegates to `startup()`.
3. **Run** — concurrently gathers `run()` coroutines for all components that override it.
4. **Shutdown** — concurrently gathers `stop()` coroutines for all components that override it.

Subclass `BaseService` to create a concrete service. Override `startup()` to inject logic that runs after components are initialized but before they start.

```python
from base_service.base_service import BaseServiceBuilder
from base_service.core.components.fastapi_component import FastAPIConfig

service = (
    BaseServiceBuilder()
    .with_fastapi(config=FastAPIConfig())
    .build()
)
service.run()
```

### `BaseComponent`

The interface every component must implement. Subclass it and provide an `initialize()` method. Override `run()` and `stop()` only for components with a long-running lifecycle.

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

### Built-in component

The builder exposes the components bundled with this library. Currently, `with_fastapi()` adds the FastAPI application and its ASGI server to the service.

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
