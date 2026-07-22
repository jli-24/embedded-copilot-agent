from __future__ import annotations

from embedded_copilot.rag.embedding import HashEmbedding


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def test_hash_embedding_is_deterministic_and_normalized() -> None:
    embedding = HashEmbedding(dimension=64)

    first = embedding.embed_query("ESP32 SPI 配置")
    second = embedding.embed_query("ESP32 SPI 配置")

    assert first == second
    assert sum(value * value for value in first) == pytest.approx(1.0)


def test_hash_embedding_prefers_shared_technical_tokens() -> None:
    embedding = HashEmbedding(dimension=64)
    query = embedding.embed_query("ESP32 SPI 配置")
    related = embedding.embed_query("ESP32 SPI controller configuration")
    unrelated = embedding.embed_query("STM32 HardFault stack frame")

    assert _dot(query, related) > _dot(query, unrelated)


import pytest
