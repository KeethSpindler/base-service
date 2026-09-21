from base_service.config.config_manager import ConfigManager, FastAPIConfig


def test_config_manager_uses_default_fastapi_config_when_none_provided() -> None:
    manager = ConfigManager()

    assert isinstance(manager.fastapi_config, FastAPIConfig)
    assert manager.fastapi_config.host == "127.0.0.1"
    assert manager.fastapi_config.port == 8000
    assert manager.fastapi_config.debug is False
    assert manager.fastapi_config.reload is False


def test_config_manager_uses_provided_fastapi_config_instance() -> None:
    config = FastAPIConfig(host="0.0.0.0", port=9000)
    manager = ConfigManager(fastapi_config=config)

    assert manager.fastapi_config is config
    assert manager.fastapi_config.host == "0.0.0.0"
    assert manager.fastapi_config.port == 9000
