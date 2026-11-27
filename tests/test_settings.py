import pytest
from pydantic import SecretStr, ValidationError, field_validator

from base_service.config.settings import ServiceSettings, settings_for_logging


class ExtendedSettings(ServiceSettings):
    database_password: SecretStr = SecretStr("database-password")
    access_token_value: str = "access-token"
    custom_private_value: str = "custom-private-value"
    metadata: dict[str, object] = {"dsn": "postgresql://user:password@host/db"}


def test_settings_load_environment_with_validated_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SERVICE_NAME", "orders")
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("LOG_LEVEL", "warning")
    monkeypatch.setenv("LOG_FORMAT", "text")
    monkeypatch.setenv("SHUTDOWN_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("HEALTH_CHECK_TIMEOUT_SECONDS", "2")

    settings = ServiceSettings()

    assert settings.service_name == "orders"
    assert settings.environment == "staging"
    assert settings.log_level == "WARNING"
    assert settings.log_format == "text"
    assert settings.shutdown_timeout_seconds == 12.5
    assert settings.health_check_timeout_seconds == 2


def test_explicit_settings_override_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SERVICE_NAME", "from-environment")
    monkeypatch.setenv("SHUTDOWN_TIMEOUT_SECONDS", "100")

    settings = ServiceSettings(
        service_name="explicit",
        shutdown_timeout_seconds=7,
    )

    assert settings.service_name == "explicit"
    assert settings.shutdown_timeout_seconds == 7


def test_legacy_logging_level_environment_name_is_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOGGING_LEVEL", "debug")

    settings = ServiceSettings(service_name="orders")

    assert settings.log_level == "DEBUG"


@pytest.mark.parametrize(
    "values",
    [
        {"service_name": ""},
        {"service_name": "orders", "environment": "  "},
        {"service_name": "orders", "log_level": "verbose"},
        {"service_name": "orders", "shutdown_timeout_seconds": 0},
        {"service_name": "orders", "health_check_timeout_seconds": -1},
    ],
)
def test_invalid_settings_fail_before_client_creation(
    values: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ServiceSettings.model_validate(values)


def test_missing_setting_reports_field_path_without_input_value() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ServiceSettings.model_validate({})

    rendered = str(exc_info.value)
    assert "service_name" in rendered
    assert "input_value" not in rendered


def test_safe_rendering_redacts_automatic_and_explicit_secrets() -> None:
    settings = ExtendedSettings(service_name="orders")

    rendered = settings_for_logging(
        settings,
        redacted_fields={"custom_private_value"},
    )

    assert rendered["database_password"] == "**********"
    assert rendered["access_token_value"] == "**********"
    assert rendered["custom_private_value"] == "**********"
    assert rendered["metadata"]["dsn"] == "**********"
    assert "database-password" not in repr(rendered)
    assert "access-token" not in repr(rendered)
    assert "postgresql://user:password@host/db" not in repr(rendered)


def test_secret_value_is_hidden_from_validation_errors() -> None:
    class InvalidSecretSettings(ServiceSettings):
        password: SecretStr

        @field_validator("password")
        @classmethod
        def reject_password(cls, value: SecretStr) -> SecretStr:
            raise ValueError("password policy failed")

    secret = "should-not-be-rendered"

    with pytest.raises(ValidationError) as exc_info:
        InvalidSecretSettings(service_name="orders", password=secret)

    rendered = str(exc_info.value)
    assert secret not in rendered
    assert "password" in rendered
