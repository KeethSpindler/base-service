"""Typed configuration shared by base services."""

import logging
from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    """Base environment-backed settings for a service."""

    model_config = SettingsConfigDict(
        extra="ignore",
        hide_input_in_errors=True,
        populate_by_name=True,
        validate_default=True,
    )

    service_name: str = Field(min_length=1)
    environment: str = Field(default="local", min_length=1)
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("LOG_LEVEL", "LOGGING_LEVEL"),
    )
    log_format: Literal["text", "json"] = "json"
    shutdown_timeout_seconds: float = Field(default=30, gt=0)
    health_check_timeout_seconds: float = Field(default=5, gt=0)

    @field_validator("service_name", "environment")
    @classmethod
    def strip_nonempty_values(cls, value: str) -> str:
        """Remove accidental surrounding whitespace from names."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Normalize and validate a standard logging level."""
        level = value.strip().upper()
        if level not in logging.getLevelNamesMapping():
            raise ValueError(f"invalid logging level: {value!r}")
        return level


_SECRET_FIELD_NAMES = {
    "api_key",
    "credential",
    "credentials",
    "dsn",
    "password",
    "secret",
    "token",
}


def _is_secret_field(field_name: str) -> bool:
    normalized = field_name.lower()
    return normalized in _SECRET_FIELD_NAMES or any(
        secret_name in normalized.split("_")
        for secret_name in _SECRET_FIELD_NAMES
    )


def _redacted_value(value: Any) -> Any:
    """Recursively redact secret values retained in custom mappings."""
    if isinstance(value, SecretStr):
        return "**********"
    if isinstance(value, Mapping):
        return {
            key: _redacted_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_redacted_value(item) for item in value]
    return value


def settings_for_logging(
    settings: BaseSettings,
    *,
    redacted_fields: Iterable[str] = (),
) -> dict[str, Any]:
    """Return a JSON-safe settings mapping with sensitive values redacted."""
    explicitly_redacted = set(redacted_fields)
    rendered = _redacted_value(settings.model_dump(mode="json"))

    def redact(mapping: dict[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in mapping.items():
            if key in explicitly_redacted or _is_secret_field(key):
                safe[key] = "**********"
            elif isinstance(value, dict):
                safe[key] = redact(value)
            else:
                safe[key] = value
        return safe

    return redact(rendered)
