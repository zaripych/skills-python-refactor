from pendant.config import Settings, DEFAULT_PORT, CONFIG_VERSION


def test_settings():
    s = Settings()
    assert s.port == DEFAULT_PORT


def test_config_version():
    assert CONFIG_VERSION == "1.0"
