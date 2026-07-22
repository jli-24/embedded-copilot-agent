from embedded_copilot.core.config import Settings
from embedded_copilot.services.config import Settings as LegacySettings


def test_foundation_settings_load_environment(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDED_COPILOT_ENVIRONMENT", "test")
    monkeypatch.setenv("EMBEDDED_COPILOT_DEBUG", "true")
    monkeypatch.setenv("EMBEDDED_COPILOT_LLM_PROVIDER", "provider-x")
    monkeypatch.setenv("EMBEDDED_COPILOT_VECTOR_STORE", "store-x")

    settings = Settings(_env_file=None)

    assert settings.environment == "test"
    assert settings.debug is True
    assert settings.llm_provider == "provider-x"
    assert settings.vector_store == "store-x"


def test_legacy_settings_import_is_compatible() -> None:
    assert LegacySettings is Settings
