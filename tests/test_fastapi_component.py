import asyncio
from contextlib import asynccontextmanager

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
    async def lifespan(app: FastAPI):
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


def test_run_creates_and_serves_configured_uvicorn_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    component = FastAPIComponent()
    created_servers = []

    class FakeServer:
        def __init__(self, config) -> None:
            self.config = config
            self.served = False
            self.should_exit = False
            created_servers.append(self)

        async def serve(self) -> None:
            self.served = True

    monkeypatch.setattr(
        "base_service.core.components.fastapi_component.uvicorn.Server", FakeServer
    )

    asyncio.run(component.run())

    server = created_servers[0]
    assert component._server is server
    assert server.served is True
    assert server.config.app is component.app
    assert server.config.host == component._config.host
    assert server.config.port == component._config.port
    assert server.config.reload == component._config.reload


def test_run_propagates_server_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    component = FastAPIComponent()

    class FailingServer:
        def __init__(self, config) -> None:
            pass

        async def serve(self) -> None:
            raise RuntimeError("server failed")

    monkeypatch.setattr(
        "base_service.core.components.fastapi_component.uvicorn.Server",
        FailingServer,
    )

    with pytest.raises(RuntimeError, match="server failed"):
        asyncio.run(component.run())


def test_stop_requests_server_shutdown() -> None:
    component = FastAPIComponent()

    class FakeServer:
        should_exit = False

    component._server = FakeServer()

    asyncio.run(component.stop())

    assert component._server.should_exit is True


def test_stop_without_running_server_is_a_noop() -> None:
    component = FastAPIComponent()

    asyncio.run(component.stop())