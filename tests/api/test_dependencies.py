from __future__ import annotations

import asyncio
from pathlib import Path

import chromadb
import pytest

from embedded_copilot.api.dependencies import (
    RuntimeInitializationError,
    build_runtime,
)
from embedded_copilot.services.config import Settings


def _settings(tmp_path: Path, knowledge_dir: Path) -> Settings:
    return Settings(
        knowledge_dir=knowledge_dir,
        chroma_path=tmp_path / "chroma",
        collection_name="runtime_test",
        embedding_dimension=64,
        chunk_size=200,
        chunk_overlap=20,
        retrieval_score_threshold=0.05,
        _env_file=None,
    )


def test_runtime_indexes_knowledge_and_answers_offline(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "spi.md").write_text(
        "# ESP32 SPI\n\nESP32 SPI configuration checks mode, clock, and chip select.",
        encoding="utf-8",
    )

    runtime = build_runtime(
        _settings(tmp_path, knowledge_dir),
        chroma_client=chromadb.EphemeralClient(),
    )
    response = asyncio.run(
        runtime.service.chat("ESP32如何配置SPI？", trace_id="trace-1")
    )

    assert runtime.health_status == "ok"
    assert response.agents_used == ["knowledge"]
    assert response.sources[0].filename == "spi.md"
    assert response.error is None


def test_runtime_applies_retrieval_score_threshold(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "spi.md").write_text(
        "# ESP32 SPI\n\nESP32 SPI configuration checks mode and clock.",
        encoding="utf-8",
    )
    settings = _settings(tmp_path, knowledge_dir).model_copy(
        update={"retrieval_score_threshold": 1.0, "retrieval_top_k": 1}
    )

    runtime = build_runtime(settings, chroma_client=chromadb.EphemeralClient())
    response = asyncio.run(
        runtime.service.chat("ESP32如何配置SPI？", trace_id="trace-policy")
    )

    assert response.sources == []
    assert response.result is not None
    assert response.result.kind == "knowledge"
    assert response.result.insufficient_context is True


def test_runtime_is_degraded_when_one_document_fails(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "spi.md").write_text("# SPI\n\nSPI mode and clock.", encoding="utf-8")
    (knowledge_dir / "broken.pdf").write_bytes(b"not-a-pdf")

    runtime = build_runtime(
        _settings(tmp_path, knowledge_dir),
        chroma_client=chromadb.EphemeralClient(),
    )

    assert runtime.health_status == "degraded"
    assert len(runtime.ingestion_errors) == 1
    assert "broken.pdf" in runtime.ingestion_errors[0]


def test_runtime_fails_when_no_supported_document_can_be_loaded(
    tmp_path: Path,
) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "broken.pdf").write_bytes(b"not-a-pdf")

    with pytest.raises(RuntimeInitializationError, match="No knowledge"):
        build_runtime(
            _settings(tmp_path, knowledge_dir),
            chroma_client=chromadb.EphemeralClient(),
        )
