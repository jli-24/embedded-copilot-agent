from __future__ import annotations

import pytest

from embedded_copilot.core.config import Settings
from embedded_copilot.vision_runtime.composition.config import (
    load_vision_runtime_config,
)


def test_vision_runtime_defaults_to_unavailable_without_model_configuration() -> None:
    settings = Settings(_env_file=None)

    config = load_vision_runtime_config(settings)

    assert config.provider == "unavailable"
    assert config.base_url is None
    assert config.model is None
    assert config.require_tls is False


@pytest.mark.parametrize(
    "base_url",
    (
        "http://localhost:11434",
        "http://127.0.0.1:11434",
        "http://[::1]:11434",
        "http://100.64.0.1:11434",
        "https://100.127.255.254:11434",
        "http://[fd7a:115c:a1e0::1]:11434",
    ),
)
def test_vision_runtime_accepts_loopback_and_tailscale_literal_endpoints(
    base_url: str,
) -> None:
    config = load_vision_runtime_config(
        Settings(
            _env_file=None,
            vision_provider="ollama",
            ollama_vision_base_url=base_url,
            ollama_vision_model="deployment-selected-model",
        )
    )

    assert config.provider == "ollama"
    assert config.base_url == base_url
    assert config.model == "deployment-selected-model"


@pytest.mark.parametrize(
    "base_url",
    (
        "http://example.com:11434",
        "http://192.168.1.10:11434",
        "http://user:secret@127.0.0.1:11434",
        "http://127.0.0.1:11434/api",
        "http://127.0.0.1:11434?token=secret",
        "http://127.0.0.1:11434#fragment",
    ),
)
def test_vision_runtime_rejects_non_private_or_credentialed_endpoints(
    base_url: str,
) -> None:
    with pytest.raises(ValueError, match="vision runtime configuration"):
        load_vision_runtime_config(
            Settings(
                _env_file=None,
                vision_provider="ollama",
                ollama_vision_base_url=base_url,
                ollama_vision_model="deployment-selected-model",
            )
        )


def test_vision_runtime_enforces_tls_when_configured() -> None:
    with pytest.raises(ValueError, match="vision runtime configuration"):
        load_vision_runtime_config(
            Settings(
                _env_file=None,
                vision_provider="ollama",
                ollama_vision_base_url="http://100.64.0.1:11434",
                ollama_vision_model="deployment-selected-model",
                ollama_vision_require_tls=True,
            )
        )


def test_vision_runtime_requires_an_explicit_model_for_ollama() -> None:
    with pytest.raises(ValueError, match="vision runtime configuration"):
        load_vision_runtime_config(
            Settings(
                _env_file=None,
                vision_provider="ollama",
                ollama_vision_model=None,
            )
        )
