from __future__ import annotations

from embedded_copilot.knowledge.entity import ExtractedEntities
from embedded_copilot.rag.metadata_filter import (
    GENERIC_CHIP,
    build_metadata_filter,
)


def test_metadata_filter_allows_exact_chip_and_generic_documents() -> None:
    entities = ExtractedEntities(chip="ESP32-S3")

    assert build_metadata_filter(entities) == {
        "$or": [{"chip": "ESP32-S3"}, {"chip": GENERIC_CHIP}]
    }


def test_metadata_filter_is_absent_without_a_chip() -> None:
    assert build_metadata_filter(ExtractedEntities()) is None
