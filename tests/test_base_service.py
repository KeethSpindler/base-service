import asyncio
from collections.abc import Awaitable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from base_service.base_service import (
    BaseService,
    BaseServiceBuilder,
    LifecycleState,
)
from base_service.core.components.base_component import BaseComponent
from base_service.core.components.fastapi_component import (
    FastAPIComponent,
    FastAPIConfig,
)
from base_service.core.enums.component_registry import ComponentRegistry
from base_service.config.settings import ServiceSettings


class RecordingComponent(BaseComponent):
    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        initialize_error: BaseException | None = None,
        run_error: BaseException | None = None,
        stop_error: BaseException | None = None,
    ) -> None:
        self.name = name
        self.events = events
        self.initialize_error = initialize_error
        self.run_error = run_error
        self.stop_error = stop_error
        self.run_called = False

    async def initialize(self) -> None:
        self.events.append(f"initialize:{self.name}")
        await asyncio.sleep(0)
        if self.initialize_error is not None:
            raise self.initialize_error

    async def run(self) -> None:
        self.run_called = True
        self.events.append(f"run:{self.name}")
        if self.run_error is not None:
            raise self.run_error

    async def stop(self) -> None:
        self.events.append(f"stop:{self.name}")
        if self.stop_error is not None:
            raise self.stop_error


class InspectableService(BaseService):
    def __init__(self, *components: BaseComponent) -> None:
        super().__init__()
        self._components.update(
            (f"test:{index}", component)
            for index, component in enumerate(components)
        )

    async def run_async(self) -> None:
        await self._run()


class BootstrapService(InspectableService):
    def __init__(self, events: list[str], *components: BaseComponent) -> None:
        super().__init__(*components)
        self.events = events

    async def bootstrap(self) -> None:
        self.events.append("bootstrap")


def test_builder_creates_fastapi_component_from_config() -> None:
    config = FastAPIConfig()
    config.title = "Configured through builder"

    service = BaseServiceBuilder().with_fastapi(config=config).build()
    component = service.get_component(ComponentRegistry.FASTAPI)

    assert isinstance(component, FastAPIComponent)
    assert component.app.title == "Configured through builder"


def test_builder_builds_supplied_service() -> None:
    custom_service = BootstrapService([], RecordingComponent("custom", []))

    service = BaseServiceBuilder(custom_service).with_fastapi().build()

    assert service is custom_service


def test_builder_applies_supplied_service_settings() -> None:
    settings = ServiceSettings(
        service_name="configured-service",
        log_format="text",
    )

    service = BaseServiceBuilder(settings=settings).build()

    assert service.settings is settings


def test_builder_with_fastapi_runs_configured_component() -> None:
    config = FastAPIConfig()
    config.title = "Configured through with_fastapi"
    server = MagicMock()
    server.serve = AsyncMock()
    server.should_exit = False

    with patch(
        "base_service.core.components.fastapi_component.uvicorn.Server",
        return_value=server,
    ) as server_class:
        service = BaseServiceBuilder().with_fastapi(config=config).build()
        service.run()

    component = service.get_component(ComponentRegistry.FASTAPI)
    assert isinstance(component, FastAPIComponent)
    assert server_class.call_args.args[0].app.title == config.title
    server.serve.assert_awaited_once_with()
    assert server.should_exit is True
    assert service.state is LifecycleState.STOPPED


def test_fastapi_registration_is_explicit_and_fluent() -> None:
    service = BaseService()
    component = FastAPIComponent()

    assert service.set_fastapi_component(component) is service
    assert service.get_component(ComponentRegistry.FASTAPI) is component

    with pytest.raises(ValueError, match="already exists"):
        service.set_fastapi_component(FastAPIComponent())


def test_fastapi_registration_rejects_other_components() -> None:
    service = BaseService()

    with pytest.raises(TypeError, match="FastAPIComponent"):
        service.set_fastapi_component(
            RecordingComponent("invalid", [])  # type: ignore[arg-type]
        )


def test_lifecycle_initializes_bootstraps_runs_and_stops_components() -> None:
    events: list[str] = []
    runner = RecordingComponent("runner", events)
    utility = RecordingComponent("utility", events)
    service = BootstrapService(events, runner, utility)

    asyncio.run(service.run_async())

    assert events == [
        "initialize:runner",
        "initialize:utility",
        "bootstrap",
        "run:runner",
        "run:utility",
        "stop:utility",
        "stop:runner",
    ]
    assert runner.run_called is True
    assert utility.run_called is True
    assert service.state is LifecycleState.STOPPED


def test_base_component_default_run_and_stop_are_noops() -> None:
    events: list[str] = []

    class UtilityComponent(BaseComponent):
        async def initialize(self) -> None:
            events.append("initialize")

    service = InspectableService(UtilityComponent())

    asyncio.run(service.run_async())

    assert events == ["initialize"]
    assert service.state is LifecycleState.STOPPED


def test_partial_initialization_stops_attempted_components_in_reverse_order() -> None:
    events: list[str] = []
    initialized = RecordingComponent("initialized", events)
    failing = RecordingComponent(
        "failing",
        events,
        initialize_error=RuntimeError("initialize failed"),
    )
    never_attempted = RecordingComponent("never-attempted", events)
    service = InspectableService(initialized, failing, never_attempted)

    with pytest.raises(RuntimeError, match="initialize failed"):
        asyncio.run(service.run_async())

    assert events == [
        "initialize:initialized",
        "initialize:failing",
        "stop:failing",
        "stop:initialized",
    ]
    assert service.state is LifecycleState.STOPPED


def test_run_failure_cancels_other_component_tasks_before_cleanup() -> None:
    events: list[str] = []
    started = asyncio.Event()

    class BlockingComponent(RecordingComponent):
        def __init__(self) -> None:
            super().__init__("blocking", events)
            self.cancelled = False

        async def run(self) -> None:
            self.run_called = True
            events.append("run:blocking")
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled = True
                events.append("cancel:blocking")
                raise

    class FailingComponent(RecordingComponent):
        async def run(self) -> None:
            await started.wait()
            await super().run()

    blocking = BlockingComponent()
    failing = FailingComponent(
        "failing",
        events,
        run_error=RuntimeError("run failed"),
    )
    service = InspectableService(blocking, failing)

    with pytest.raises(RuntimeError, match="run failed"):
        asyncio.run(service.run_async())

    assert blocking.cancelled is True
    assert events[-2:] == ["stop:failing", "stop:blocking"]


def test_shutdown_is_reverse_ordered_and_idempotent() -> None:
    events: list[str] = []
    service = InspectableService(
        RecordingComponent("first", events),
        RecordingComponent("second", events),
    )
    asyncio.run(service.run_async())

    asyncio.run(service.shutdown())

    assert events == [
        "initialize:first",
        "initialize:second",
        "run:first",
        "run:second",
        "stop:second",
        "stop:first",
    ]
    assert service.state is LifecycleState.STOPPED


def test_shutdown_continues_after_failures_and_groups_errors() -> None:
    events: list[str] = []
    service = InspectableService(
        RecordingComponent(
            "first",
            events,
            stop_error=RuntimeError("first failed"),
        ),
        RecordingComponent(
            "second",
            events,
            stop_error=ValueError("second failed"),
        ),
    )

    with pytest.raises(ExceptionGroup) as exc_info:
        asyncio.run(service.run_async())

    assert len(exc_info.value.exceptions) == 2
    assert events[-2:] == ["stop:second", "stop:first"]
    assert service.state is LifecycleState.FAILED


def test_single_cleanup_failure_is_not_wrapped() -> None:
    service = InspectableService(
        RecordingComponent(
            "component",
            [],
            stop_error=RuntimeError("stop failed"),
        )
    )

    with pytest.raises(RuntimeError, match="stop failed"):
        asyncio.run(service.run_async())


def test_cancelled_run_waits_for_cleanup_to_finish() -> None:
    stop_started = asyncio.Event()
    allow_stop = asyncio.Event()

    class SlowStopComponent(RecordingComponent):
        async def stop(self) -> None:
            stop_started.set()
            await allow_stop.wait()

    async def exercise_cancellation() -> None:
        service = InspectableService(SlowStopComponent("component", []))
        run_task = asyncio.create_task(service.run_async())
        await stop_started.wait()

        run_task.cancel()
        await asyncio.sleep(0)
        assert run_task.done() is False

        allow_stop.set()
        with pytest.raises(asyncio.CancelledError):
            await run_task
        assert service.state is LifecycleState.STOPPED

    asyncio.run(exercise_cancellation())


def test_run_and_shutdown_failures_are_both_reported() -> None:
    service = InspectableService(
        RecordingComponent(
            "component",
            [],
            run_error=RuntimeError("run failed"),
            stop_error=RuntimeError("stop failed"),
        )
    )

    with pytest.raises(BaseExceptionGroup) as exc_info:
        asyncio.run(service.run_async())

    assert len(exc_info.value.exceptions) == 2
    assert str(exc_info.value.exceptions[0]) == "run failed"
    assert str(exc_info.value.exceptions[1]) == "stop failed"


@pytest.mark.parametrize(
    "run_error",
    [KeyboardInterrupt(), SystemExit("exit"), RuntimeError("failure")],
)
def test_run_errors_are_reraised_after_cleanup(
    run_error: BaseException,
) -> None:
    events: list[str] = []

    class FailingComponent(RecordingComponent):
        async def run(self) -> None:
            events.append("run")
            raise run_error

    service = InspectableService(FailingComponent("component", events))

    match = str(run_error) or None
    with pytest.raises(type(run_error), match=match):
        asyncio.run(service.run_async())

    assert events[-1] == "stop:component"


def test_service_cannot_register_or_start_after_lifecycle_begins() -> None:
    service = InspectableService()
    asyncio.run(service.run_async())

    with pytest.raises(RuntimeError, match="cannot start"):
        asyncio.run(service.run_async())
    with pytest.raises(RuntimeError, match="cannot register"):
        service.set_fastapi_component(FastAPIComponent())


def test_run_owns_event_loop_and_uses_lifecycle_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = BaseService()
    received: list[Awaitable[None]] = []

    def fake_asyncio_run(coroutine: Awaitable[Any]) -> None:
        received.append(coroutine)
        coroutine.close()  # type: ignore[attr-defined]

    monkeypatch.setattr(
        "base_service.base_service.asyncio.run",
        fake_asyncio_run,
    )

    service.run()

    assert len(received) == 1
