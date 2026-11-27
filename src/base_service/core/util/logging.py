"""Structured logging and correlation context helpers."""

import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any, Generator, Literal

from base_service.config.settings import ServiceSettings

_correlation_id: ContextVar[str | None] = ContextVar(
    "base_service_correlation_id",
    default=None,
)
_HANDLER_MARKER = "_base_service_handler"
_LOG_FIELDS = (
    "service",
    "component",
    "event",
    "action",
    "lifecycle_state",
    "correlation_id",
)


def get_correlation_id() -> str | None:
    """Return the correlation identifier in the current execution context."""
    return _correlation_id.get()


def set_correlation_id(correlation_id: str | None) -> Token[str | None]:
    """Set a correlation identifier and return the context reset token."""
    return _correlation_id.set(correlation_id)


def reset_correlation_id(token: Token[str | None]) -> None:
    """Restore the correlation identifier represented by a token."""
    _correlation_id.reset(token)


@contextmanager
def correlation_context(correlation_id: str | None) -> Generator[None, None, None]:
    """Scope a correlation identifier to synchronous or awaited work."""
    token = set_correlation_id(correlation_id)
    try:
        yield
    finally:
        reset_correlation_id(token)


class ComponentLoggerAdapter(logging.LoggerAdapter[logging.Logger]):
    """Logger adapter that supplies component-level structured fields."""

    def process(
        self,
        msg: object,
        kwargs: Any,
    ) -> tuple[object, dict[str, Any]]:
        extra = dict(self.extra or {})
        extra.update(kwargs.pop("extra", {}))
        extra.setdefault("correlation_id", get_correlation_id())
        kwargs["extra"] = extra
        return msg, kwargs


class _StructuredFormatter(logging.Formatter):
    def __init__(self, log_format: Literal["text", "json"]) -> None:
        super().__init__()
        self.log_format = log_format

    def format(self, record: logging.LogRecord) -> str:
        fields = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=UTC,
            ).isoformat(timespec="seconds"),
            "service": getattr(record, "service", record.name.split(".", 1)[0]),
            "component": getattr(record, "component", record.name),
            "event": getattr(record, "event", record.funcName),
            "action": getattr(record, "action", record.funcName),
            "lifecycle_state": getattr(record, "lifecycle_state", "unknown"),
            "severity": record.levelname,
            "correlation_id": getattr(
                record,
                "correlation_id",
                get_correlation_id(),
            ),
            "message": record.getMessage(),
        }
        if record.exc_info:
            fields["exception"] = self.formatException(record.exc_info)

        if self.log_format == "json":
            return json.dumps(fields, separators=(",", ":"), ensure_ascii=True)

        metadata = " ".join(
            f"{name}={fields[name]!r}"
            for name in _LOG_FIELDS
            if fields[name] is not None
        )
        rendered = (
            f"[{fields['timestamp']} | {fields['severity']}] "
            f"{metadata} {fields['message']}"
        )
        if "exception" in fields:
            rendered = f"{rendered}\n{fields['exception']}"
        return rendered


def configure_logging(settings: ServiceSettings) -> logging.Logger:
    """Configure one idempotent handler for a service logger tree."""
    return instantiate_logger(
        settings.service_name,
        settings.log_level,
        log_format=settings.log_format,
    )


def instantiate_logger(
    service_name: str,
    logging_level: str,
    *,
    log_format: Literal["text", "json"] = "text",
) -> logging.Logger:
    """Create or update a service logger without duplicating handlers."""
    normalized_level = logging_level.strip().upper()
    level = logging.getLevelNamesMapping().get(normalized_level)
    if not isinstance(level, int):
        raise ValueError(f"invalid logging level: {logging_level!r}")

    logger = logging.getLogger(service_name)
    logger.setLevel(level)
    logger.propagate = False

    owned_handlers = [
        handler
        for handler in logger.handlers
        if getattr(handler, _HANDLER_MARKER, False)
    ]
    if owned_handlers:
        handler = owned_handlers[0]
        for duplicate in owned_handlers[1:]:
            logger.removeHandler(duplicate)
            duplicate.close()
    else:
        handler = logging.StreamHandler()
        setattr(handler, _HANDLER_MARKER, True)
        logger.addHandler(handler)
    handler.setLevel(level)
    handler.setFormatter(_StructuredFormatter(log_format))
    return logger


def get_component_logger(
    service_name: str,
    component: str,
) -> ComponentLoggerAdapter:
    """Return a structured logger bound to a service component."""
    logger = logging.getLogger(f"{service_name}.{component}")
    return ComponentLoggerAdapter(
        logger,
        {
            "service": service_name,
            "component": component,
        },
    )
