from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application settings with foundation extension points."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EMBEDDED_COPILOT_",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_name: str = "Embedded Copilot Agent"
    version: Literal["0.11.0"] = "0.11.0"
    environment: str = "development"
    debug: bool = False
    llm_provider: str | None = None
    vector_store: str | None = None
    runtime_mode: Literal["offline", "llm"] = "offline"
    knowledge_dir: Path = Path("knowledge")
    chroma_path: Path = Path(".data/chroma")
    collection_name: str = "embedded_copilot_v01"
    embedding_provider: Literal["local_hash", "openai_compatible"] = "local_hash"
    embedding_dimension: int = Field(default=384, ge=64, le=4096)
    chat_model: str | None = None
    embedding_model: str | None = None
    openai_base_url: HttpUrl | None = None
    openai_api_key: SecretStr | None = None
    chunk_size: int = Field(default=800, ge=100, le=8000)
    chunk_overlap: int = Field(default=100, ge=0, le=2000)
    retrieval_top_k: int = Field(default=4, ge=1, le=20)
    retrieval_score_threshold: float = Field(default=0.15, ge=0.0, le=1.0)
    request_timeout_seconds: float = Field(default=10.0, gt=0.0, le=120.0)

    @model_validator(mode="after")
    def validate_chunk_window(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self
