# base-service

Foundation library for building component-driven microservices. Provides a `BaseService` container, a fluent builder, and reusable components.

## Concepts

### `BaseService`

The service container. Manages the lifecycle of all registered components:

1. **Initialize** — awaits `initialize()` on every component in registration order.
2. **Bootstrap** — runs the overridable `bootstrap()` hook for pre-run service logic.
3. **Run** — runs every component's async `run()` method concurrently.
4. **Shutdown** — awaits `stop()` in reverse registration order, including after
   partial startup.

Subclass `BaseService` to create a concrete service. Override `bootstrap()` to
inject logic that runs after components are initialized but before they start.

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

The interface every component must implement. Subclass it and provide an
`initialize()` method. Override `run()` and `stop()` when the component owns
runtime work or resources.

| Method | Required | Purpose |
|---|---|---|
| `initialize()` | Yes | One-time async setup (config loading, client creation, etc.) |
| `run()` | No | Concurrent async runtime work. Base implementation is a no-op. |
| `stop()` | No | Async cleanup called for every attempted component. |

Components implement lifecycle methods asynchronously. Utility components can
keep the base `run()` and `stop()` no-op methods.

```python
class MyComponent(BaseComponent):
    async def initialize(self):
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
