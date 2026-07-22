from __future__ import annotations

from embedded_copilot.knowledge.entity import (
    EmbeddedEntityExtractor,
    ExtractedEntities,
)
from embedded_copilot.rag.metadata_filter import build_metadata_filter
from embedded_copilot.rag.retriever import ChromaRetriever, RetrievedChunk


_FRAMEWORK_DOCUMENT_TYPES = {
    "ESP-IDF": {"esp_idf"},
    "STM32 HAL": {"hal", "stm32_hal"},
    "FreeRTOS": {"freertos"},
}


def _entity_rank(chunk: RetrievedChunk, entities: ExtractedEntities) -> int:
    rank = 0
    text = chunk.text.casefold()
    chapter = (chunk.metadata.chapter or "").casefold()
    for protocol in entities.protocols:
        if chapter == protocol.casefold():
            rank += 2
        elif protocol.casefold() in text:
            rank += 1

    document_type = (chunk.metadata.document_type or "").casefold()
    for framework in entities.frameworks:
        expected_types = _FRAMEWORK_DOCUMENT_TYPES.get(framework, set())
        if document_type in expected_types:
            rank += 2
        elif framework.casefold() in text:
            rank += 1

    classified = set(entities.protocols) | set(entities.frameworks)
    for feature in entities.features:
        if feature not in classified and feature.casefold() in text:
            rank += 1
    return rank


def _chip_tier(chunk: RetrievedChunk, entities: ExtractedEntities) -> int:
    return int(entities.chip is not None and chunk.metadata.chip == entities.chip)


class HybridRetriever:
    def __init__(
        self,
        *,
        retriever: ChromaRetriever,
        entity_extractor: EmbeddedEntityExtractor | None = None,
        candidate_multiplier: int = 3,
    ) -> None:
        if candidate_multiplier < 1:
            raise ValueError("candidate_multiplier must be positive")
        self._retriever = retriever
        self._entity_extractor = entity_extractor or EmbeddedEntityExtractor()
        self._candidate_multiplier = candidate_multiplier

    def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        score_threshold: float,
    ) -> list[RetrievedChunk]:
        entities = self._entity_extractor.extract(query)
        candidates = self._retriever.retrieve_filtered(
            query,
            top_k=top_k * self._candidate_multiplier,
            score_threshold=score_threshold,
            metadata_filter=build_metadata_filter(entities),
        )
        ranked = sorted(
            candidates,
            key=lambda chunk: (
                _chip_tier(chunk, entities),
                _entity_rank(chunk, entities),
                chunk.citation.score,
            ),
            reverse=True,
        )
        return ranked[:top_k]
