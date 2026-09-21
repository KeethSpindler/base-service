import asyncio
from enum import auto

import pytest

from base_service.base_service import BaseService, BaseServiceBuilder
from base_service.core.components.base_component import BaseComponent
from base_service.core.enums.component_registry import ComponentRegistry


class ServiceRegistry(ComponentRegistry):
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


class ServiceWithStartup(BaseService):
	def __init__(self) -> None:
		super().__init__()
		self.bootstrap_called = False

	async def bootstrap(self) -> None:
		self.bootstrap_called = True


def test_builder_registers_components_and_builds_service() -> None:
	runner = RunComponent()

	service = (
		BaseServiceBuilder()
		.with_component(ServiceRegistry.RUNNER, runner)
		.build()
	)

	assert isinstance(service, BaseService)


def test_add_component_raises_on_duplicate_registry_key() -> None:
	service = BaseService()
	first = RunComponent()
	second = UtilityComponent()

	service.add_component(ServiceRegistry.RUNNER, first)

	with pytest.raises(ValueError, match="already exists"):
		service.add_component(ServiceRegistry.RUNNER, second)


def test_run_initializes_components_calls_startup_and_only_overridden_run() -> None:
	service = ServiceWithStartup()
	runner = RunComponent()
	utility = UtilityComponent()

	service.add_component(ServiceRegistry.RUNNER, runner)
	service.add_component(ServiceRegistry.UTILITY, utility)

	asyncio.run(service.run())

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


def test_start_propagates_keyboard_interrupt_after_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
	service = BaseService()
	events: list[str] = []

	async def fake_run() -> None:
		events.append("run")
		raise KeyboardInterrupt()

	async def fake_shutdown() -> None:
		events.append("shutdown")

	service.run = fake_run  # type: ignore[method-assign]
	service.shutdown = fake_shutdown  # type: ignore[method-assign]

	def fake_asyncio_run(coro):
		return asyncio.new_event_loop().run_until_complete(coro)

	monkeypatch.setattr("base_service.base_service.asyncio.run", fake_asyncio_run)

	with pytest.raises(KeyboardInterrupt):
		service.start()

	assert events == ["run", "shutdown"]


def test_start_calls_shutdown_and_reraises_unhandled_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
	service = BaseService()
	events: list[str] = []

	async def fake_run() -> None:
		events.append("run")
		raise RuntimeError("boom")

	async def fake_shutdown() -> None:
		events.append("shutdown")

	service.run = fake_run  # type: ignore[method-assign]
	service.shutdown = fake_shutdown  # type: ignore[method-assign]

	def fake_asyncio_run(coro):
		return asyncio.new_event_loop().run_until_complete(coro)

	monkeypatch.setattr("base_service.base_service.asyncio.run", fake_asyncio_run)

	with pytest.raises(RuntimeError, match="boom"):
		service.start()

	assert events == ["run", "shutdown"]
