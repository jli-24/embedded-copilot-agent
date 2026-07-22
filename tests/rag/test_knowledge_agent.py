from __future__ import annotations

import asyncio

from embedded_copilot.agents.knowledge import KnowledgeAgent
from embedded_copilot.agents.workflow import create_initial_state
from embedded_copilot.knowledge.models import DocumentMetadata
from embedded_copilot.rag.retriever import RetrievedChunk
from embedded_copilot.schemas.result import SourceCitation
from embedded_copilot.services.llm import OfflineLLMService
from embedded_copilot.tools.document_tool import DocumentSearchTool


class StaticRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks

    def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        score_threshold: float,
    ) -> list[RetrievedChunk]:
        return self._chunks[:top_k]


def _cited_chunk() -> RetrievedChunk:
    citation = SourceCitation(
        source="esp32/esp32_s3/datasheet/manual.pdf",
        filename="manual.pdf",
        page=45,
        chunk_id="spi-page-45",
        score=0.91,
    )
    return RetrievedChunk(
        chunk_id="spi-page-45",
        text="ESP32-S3 SPI chapter context.",
        citation=citation,
        metadata=DocumentMetadata(
            chip="ESP32-S3",
            chapter="SPI",
            page=45,
            document_type="datasheet",
        ),
    )


def test_knowledge_agent_maps_chapter_without_changing_citation() -> None:
    chunk = _cited_chunk()
    tool = DocumentSearchTool(
        retriever=StaticRetriever([chunk]),
        llm=OfflineLLMService(),
        timeout_seconds=1.0,
    )
    state = create_initial_state("ESP32-S3 SPI", trace_id="trace-chapter")

    update = asyncio.run(KnowledgeAgent(tool=tool).run(state))

    result = update["results"][0]
    assert result.kind == "knowledge"
    assert result.sources == [chunk.citation]
    assert update["sources"] == [chunk.citation]
    assert "manual.pdf, chapter SPI, page 45" in update["final_answer"]


def test_knowledge_agent_preserves_insufficient_context() -> None:
    tool = DocumentSearchTool(
        retriever=StaticRetriever([]),
        llm=OfflineLLMService(),
        timeout_seconds=1.0,
    )
    state = create_initial_state("unknown device", trace_id="trace-empty")

    update = asyncio.run(KnowledgeAgent(tool=tool).run(state))

    result = update["results"][0]
    assert result.kind == "knowledge"
    assert result.insufficient_context is True
    assert result.sources == []
