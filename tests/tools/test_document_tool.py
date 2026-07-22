from __future__ import annotations

import asyncio
import time

import pytest
from pydantic import ValidationError

from embedded_copilot.rag.retriever import RetrievedChunk
from embedded_copilot.schemas.result import ErrorCode, SourceCitation, ToolStatus
from embedded_copilot.services.llm import OfflineLLMService
from embedded_copilot.tools.document_tool import (
    DocumentSearchInput,
    DocumentSearchTool,
)


class FakeRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks

    def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        score_threshold: float,
    ) -> list[RetrievedChunk]:
        return self.chunks[:top_k]


class SlowRetriever(FakeRetriever):
    def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        score_threshold: float,
    ) -> list[RetrievedChunk]:
        time.sleep(0.05)
        return super().retrieve(
            query,
            top_k=top_k,
            score_threshold=score_threshold,
        )


def _chunk() -> RetrievedChunk:
    citation = SourceCitation(
        source="knowledge/embedded_basics.md",
        filename="embedded_basics.md",
        page=None,
        chunk_id="spi-chunk",
        score=0.9,
    )
    return RetrievedChunk(
        chunk_id="spi-chunk",
        text="ESP32 SPI configuration must identify mode, clock and chip select.",
        citation=citation,
    )


def test_document_tool_returns_grounded_answer_and_citations() -> None:
    tool = DocumentSearchTool(
        retriever=FakeRetriever([_chunk()]),
        llm=OfflineLLMService(),
        timeout_seconds=1.0,
    )

    result = asyncio.run(tool.invoke(DocumentSearchInput(query="ESP32 SPI")))

    assert result.status is ToolStatus.SUCCESS
    assert result.data is not None
    assert result.data.insufficient_context is False
    assert result.data.items[0].citation.chunk_id == "spi-chunk"
    assert "ESP32 SPI" in result.data.answer


def test_document_tool_reports_insufficient_context() -> None:
    tool = DocumentSearchTool(
        retriever=FakeRetriever([]),
        llm=OfflineLLMService(),
        timeout_seconds=1.0,
    )

    result = asyncio.run(tool.invoke(DocumentSearchInput(query="unknown part")))

    assert result.status is ToolStatus.SUCCESS
    assert result.data is not None
    assert result.data.insufficient_context is True
    assert result.data.items == []


def test_document_tool_maps_timeout() -> None:
    tool = DocumentSearchTool(
        retriever=SlowRetriever([_chunk()]),
        llm=OfflineLLMService(),
        timeout_seconds=0.001,
    )

    result = asyncio.run(tool.invoke(DocumentSearchInput(query="ESP32 SPI")))

    assert result.status is ToolStatus.ERROR
    assert result.error is not None
    assert result.error.code is ErrorCode.TIMEOUT


def test_document_search_input_rejects_blank_query() -> None:
    with pytest.raises(ValidationError):
        DocumentSearchInput(query="   ")
