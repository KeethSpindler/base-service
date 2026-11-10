from base_service.core.components.fastapi_component import FastAPIConfig


def test_fastapi_config_uses_defaults_when_environment_is_unset(monkeypatch) -> None:
    for key in (
        "FASTAPI_HOST",
        "FASTAPI_PORT",
        "FASTAPI_DEBUG",
        "FASTAPI_RELOAD",
        "FASTAPI_CORS",
    ):
        monkeypatch.delenv(key, raising=False)

    config = FastAPIConfig()

    assert config.host == "127.0.0.1"
    assert config.port == 8000
    assert config.debug is False
    assert config.reload is False
    assert config.cors == ["*"]


def test_fastapi_config_environment_overrides_explicit_defaults(monkeypatch) -> None:
    monkeypatch.setenv("FASTAPI_HOST", "0.0.0.0")
    monkeypatch.setenv("FASTAPI_PORT", "9000")
    monkeypatch.setenv("FASTAPI_DEBUG", "yes")
    monkeypatch.setenv("FASTAPI_RELOAD", "1")
    monkeypatch.setenv("FASTAPI_CORS", "https://one.example,https://two.example")

    config = FastAPIConfig(host="localhost", port=7000)

    assert config.host == "0.0.0.0"
    assert config.port == 9000
    assert config.debug is True
    assert config.reload is True
    assert config.cors == ["https://one.example", "https://two.example"]
