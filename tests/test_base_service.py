import asyncio
from enum import StrEnum, auto

import pytest

from base_service.base_service import BaseService, BaseServiceBuilder
from base_service.core.components.base_component import BaseComponent
from base_service.core.components.fastapi_component import FastAPIConfig
from base_service.core.enums.component_registry import ComponentRegistry


class ServiceRegistry(StrEnum):
	RUNNER = auto()
	UTILITY = auto()


class RunComponent(BaseComponent):
	def __init__(self) -> None:
		self.initialized = False
		self.ran = False
		self.stopped = False

	def initialize(self):
		self.initialized = True

	async def run(self) -> None:
		self.ran = True

	async def stop(self) -> None:
		self.stopped = True


class UtilityComponent(BaseComponent):
	def __init__(self) -> None:
		self.initialized = False

	def initialize(self):
		self.initialized = True

	async def run(self) -> None:
		pass

	async def stop(self) -> None:
		pass


class ServiceWithStartup(BaseService):
	def __init__(self) -> None:
		super().__init__()
		self.bootstrap_called = False

	async def bootstrap(self) -> None:
		self.bootstrap_called = True


def test_builder_creates_fastapi_component_from_config() -> None:
	config = FastAPIConfig()
	config.title = "Configured through builder"

	service = BaseServiceBuilder().with_fastapi(config=config).build()

	assert service._components[ComponentRegistry.FASTAPI].app.title == config.title


def test_builder_with_fastapi_runs_configured_component(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	config = FastAPIConfig()
	config.title = "Configured through with_fastapi"
	servers = []

	class FakeServer:
		def __init__(self, uvicorn_config) -> None:
			self.config = uvicorn_config
			self.served = False
			self.should_exit = False
			servers.append(self)

		async def serve(self) -> None:
			self.served = True

	monkeypatch.setattr(
		"base_service.core.components.fastapi_component.uvicorn.Server", FakeServer
	)

	service = BaseServiceBuilder().with_fastapi(config=config).build()
	service.run()

	server = servers[0]
	assert server.config.app.title == config.title
	assert server.served is True
	assert server.should_exit is True


def test_add_component_raises_on_duplicate_registry_key() -> None:
	service = BaseService()
	first = RunComponent()
	second = UtilityComponent()

	service.add_component(ComponentRegistry.FASTAPI, first)

	with pytest.raises(ValueError, match="already exists"):
		service.add_component(ComponentRegistry.FASTAPI, second)


def test_run_initializes_components_calls_startup_and_only_overridden_run() -> None:
	service = ServiceWithStartup()
	runner = RunComponent()
	utility = UtilityComponent()

	service.add_component(ServiceRegistry.RUNNER, runner)
	service.add_component(ServiceRegistry.UTILITY, utility)

	asyncio.run(service._run_services())

	assert runner.initialized is True
	assert utility.initialized is True
	assert service.bootstrap_called is True
	assert runner.ran is True


def test_shutdown_only_calls_overridden_stop() -> None:
	service = BaseService()
	runner = RunComponent()
	utility = UtilityComponent()

	service.add_component(ServiceRegistry.RUNNER, runner)
	service.add_component(ServiceRegistry.UTILITY, utility)

	asyncio.run(service.shutdown())

	assert runner.stopped is True


def test_startup_hook_runs_after_components_initialize() -> None:
	events: list[str] = []

	class Component(BaseComponent):
		def initialize(self) -> None:
			events.append("initialize")

	class Service(BaseService):
		async def startup(self) -> None:
			events.append("startup")

	service = Service()
	service.add_component(ServiceRegistry.UTILITY, Component())

	asyncio.run(service._run_services())

	assert events == ["initialize", "startup"]


def test_base_component_default_run_and_stop_are_noops() -> None:
	class Utility(BaseComponent):
		def initialize(self) -> None:
			pass

	component = Utility()

	async def run_lifecycle_methods() -> None:
		await component.run()
		await component.stop()

	asyncio.run(run_lifecycle_methods())


def test_start_propagates_keyboard_interrupt_after_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
	service = BaseService()
	events: list[str] = []

	async def fake_run() -> None:
		events.append("run")
		raise KeyboardInterrupt()

	async def fake_shutdown() -> None:
		events.append("shutdown")

	service._run_services = fake_run  # type: ignore[method-assign]
	service.shutdown = fake_shutdown  # type: ignore[method-assign]

	def fake_asyncio_run(coro):
		return asyncio.new_event_loop().run_until_complete(coro)

	monkeypatch.setattr("base_service.base_service.asyncio.run", fake_asyncio_run)

	with pytest.raises(KeyboardInterrupt):
		service.run()

	assert events == ["run", "shutdown"]


def test_start_calls_shutdown_and_reraises_unhandled_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
	service = BaseService()
	events: list[str] = []

	async def fake_run() -> None:
		events.append("run")
		raise RuntimeError("boom")

	async def fake_shutdown() -> None:
		events.append("shutdown")

	service._run_services = fake_run  # type: ignore[method-assign]
	service.shutdown = fake_shutdown  # type: ignore[method-assign]

	def fake_asyncio_run(coro):
		return asyncio.new_event_loop().run_until_complete(coro)

	monkeypatch.setattr("base_service.base_service.asyncio.run", fake_asyncio_run)

	with pytest.raises(RuntimeError, match="boom"):
		service.run()

	assert events == ["run", "shutdown"]
