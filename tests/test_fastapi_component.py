import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import APIRouter, FastAPI

from base_service.core.components.fastapi_component import FastAPIComponent, FastAPIConfig


def test_component_creates_app_from_config() -> None:
    config = FastAPIConfig(host="0.0.0.0", port=9000)
    config.title = "Orders"
    config.description = "Order service"
    config.version = "1.2.3"
    config.debug = True

    component = FastAPIComponent(config=config)

    assert component.app.title == "Orders"
    assert component.app.description == "Order service"
    assert component.app.version == "1.2.3"
    assert component.app.debug is True


def test_component_uses_provided_app() -> None:
    app = FastAPI(title="Provided app")

    component = FastAPIComponent(app=app)

    assert component.app is app


def test_attach_lifespan_registers_callable() -> None:
    component = FastAPIComponent()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield

    component.attach_lifespan(lifespan)

    assert component.app.router.lifespan_context is lifespan


def test_attach_lifespan_rejects_non_callable() -> None:
    component = FastAPIComponent()

    with pytest.raises(ValueError, match="Lifespan must be a viable callable"):
        component.attach_lifespan(None)


def test_add_api_router_registers_routes() -> None:
    component = FastAPIComponent()
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    component.add_api_router(router)

    assert component.app.url_path_for("health") == "/health"


def test_add_api_router_rejects_non_router() -> None:
    component = FastAPIComponent()

    with pytest.raises(ValueError, match="router must be an instance of APIRouter"):
        component.add_api_router(None)


def test_run_creates_and_serves_configured_uvicorn_server() -> None:
    config = FastAPIConfig(host="127.0.0.1", port=8000)
    component = FastAPIComponent(config=config)
    server = MagicMock()
    server.serve = AsyncMock()

    with patch(
        "base_service.core.components.fastapi_component.uvicorn.Server",
        return_value=server,
    ) as server_class:
        asyncio.run(component.run())

    server.serve.assert_awaited_once_with()
    assert server_class.call_args.args[0].app is component.app
    assert server_class.call_args.args[0].host == config.host
    assert server_class.call_args.args[0].port == config.port
    assert server_class.call_args.args[0].reload == config.reload


def test_run_propagates_server_errors() -> None:
    component = FastAPIComponent()
    server = MagicMock()
    server.serve = AsyncMock(side_effect=RuntimeError("server failed"))

    with patch(
        "base_service.core.components.fastapi_component.uvicorn.Server",
        return_value=server,
    ):
        with pytest.raises(RuntimeError, match="server failed"):
            asyncio.run(component.run())


def test_stop_requests_server_shutdown() -> None:
    component = FastAPIComponent()
    server = MagicMock(should_exit=False)
    server.serve = AsyncMock()

    with patch(
        "base_service.core.components.fastapi_component.uvicorn.Server",
        return_value=server,
    ):
        asyncio.run(component.run())
        asyncio.run(component.stop())

    assert server.should_exit is True


def test_stop_without_running_server_is_a_noop() -> None:
    component = FastAPIComponent()

    asyncio.run(component.stop())


def test_initialize_is_async_noop() -> None:
    component = FastAPIComponent()

    asyncio.run(component.initialize())