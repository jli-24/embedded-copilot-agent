from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from embedded_copilot import __version__
from embedded_copilot.services.config import Settings


def test_settings_have_v037_offline_defaults() -> None:
    settings = Settings(_env_file=None)

    assert __version__ == "0.37.0"
    assert settings.version == "0.37.0"
    assert settings.runtime_mode == "offline"
    assert settings.chunk_size == 800
    assert settings.chunk_overlap == 100
    assert settings.retrieval_top_k == 4
    assert settings.embedding_dimension == 384


def test_chunk_overlap_must_be_smaller_than_chunk_size() -> None:
    with pytest.raises(ValidationError):
        Settings(chunk_size=100, chunk_overlap=100, _env_file=None)


def test_api_key_is_redacted_from_repr() -> None:
    settings = Settings(openai_api_key="super-secret", _env_file=None)

    assert "super-secret" not in repr(settings)


def test_example_environment_loads_in_offline_mode() -> None:
    example_env = Path(__file__).resolve().parents[2] / ".env.example"

    settings = Settings(_env_file=example_env)

    assert settings.runtime_mode == "offline"
    assert settings.openai_base_url is None
    assert settings.openai_api_key is None
    assert settings.chat_model is None
    assert settings.embedding_model is None
