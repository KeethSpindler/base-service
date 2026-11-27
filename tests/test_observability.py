import asyncio
import json
import logging

import pytest

from base_service.core.util.logging import (
    configure_logging,
    correlation_context,
    get_component_logger,
    get_correlation_id,
    instantiate_logger,
    reset_correlation_id,
    set_correlation_id,
)
from base_service.config.settings import ServiceSettings


def test_logging_configuration_is_idempotent() -> None:
    settings = ServiceSettings(
        service_name="logging-idempotent",
        log_format="json",
    )

    first = configure_logging(settings)
    configure_logging(settings)
    configure_logging(settings)

    owned_handlers = [
        handler
        for handler in first.handlers
        if getattr(handler, "_base_service_handler", False)
    ]
    assert len(owned_handlers) == 1


def test_json_logging_records_consistent_context(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = ServiceSettings(
        service_name="logging-json",
        log_level="INFO",
        log_format="json",
    )
    configure_logging(settings)
    logger = get_component_logger(settings.service_name, "Worker")

    with correlation_context("request-123"):
        logger.info(
            "Task accepted",
            extra={
                "event": "task.accepted",
                "action": "accept",
                "lifecycle_state": "running",
            },
        )

    record = json.loads(capsys.readouterr().err.strip())
    assert record["service"] == "logging-json"
    assert record["component"] == "Worker"
    assert record["event"] == "task.accepted"
    assert record["action"] == "accept"
    assert record["lifecycle_state"] == "running"
    assert record["severity"] == "INFO"
    assert record["correlation_id"] == "request-123"
    assert record["message"] == "Task accepted"


def test_text_logging_includes_exception_information(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = ServiceSettings(
        service_name="logging-text",
        log_format="text",
    )
    configure_logging(settings)
    logger = get_component_logger(settings.service_name, "Worker")

    try:
        raise RuntimeError("failed operation")
    except RuntimeError:
        logger.exception("Operation failed")

    rendered = capsys.readouterr().err
    assert "service='logging-text'" in rendered
    assert "component='Worker'" in rendered
    assert "Operation failed" in rendered
    assert "RuntimeError: failed operation" in rendered


def test_correlation_context_survives_awaited_operations() -> None:
    async def read_after_yield() -> str | None:
        await asyncio.sleep(0)
        return get_correlation_id()

    async def exercise() -> tuple[str | None, str | None, str | None]:
        with correlation_context("parent"):
            child_value = await read_after_yield()
            async_value = await asyncio.create_task(read_after_yield())
            return (
                child_value,
                async_value,
                get_correlation_id(),
            )

    values = asyncio.run(exercise())

    assert values == ("parent", "parent", "parent")
    assert get_correlation_id() is None


def test_correlation_context_resets_after_failure() -> None:
    with pytest.raises(RuntimeError, match="failure"):
        with correlation_context("temporary"):
            raise RuntimeError("failure")

    assert get_correlation_id() is None


def test_explicit_correlation_token_can_be_reset() -> None:
    token = set_correlation_id("direct")

    assert get_correlation_id() == "direct"

    reset_correlation_id(token)
    assert get_correlation_id() is None


def test_invalid_direct_log_level_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid logging level"):
        instantiate_logger("invalid-level", "chatty")


def test_reconfiguration_preserves_unowned_handler() -> None:
    logger = logging.getLogger("logging-preserve")
    unowned = logging.NullHandler()
    logger.addHandler(unowned)
    logger_name = logger.name

    try:
        configure_logging(
            ServiceSettings(service_name=logger_name, log_level="DEBUG")
        )
        configure_logging(
            ServiceSettings(service_name=logger_name, log_level="INFO")
        )

        assert unowned in logger.handlers
        assert logger.level == logging.INFO
    finally:
        logger.handlers.clear()
