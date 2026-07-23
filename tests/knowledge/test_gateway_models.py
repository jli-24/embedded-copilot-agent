import math

import pytest
from pydantic import ValidationError

from embedded_copilot.knowledge.models import (
    DocumentMetadata,
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)


def test_gateway_models_preserve_document_metadata_contract() -> None:
    metadata = DocumentMetadata(chip=" ESP32-S3 ", page=1)

    assert metadata.chip == "ESP32-S3"
    assert metadata.page == 1


def test_gateway_models_strip_and_normalize_sources_stably() -> None:
    result = KnowledgeResult(
        id=" doc-1 ",
        title=" SPI Guide ",
        content=" Technical content ",
        source="local",
        score=2,
    )
    query = KnowledgeQuery(
        query=" SPI layout ",
        sources=["local", "LOCAL", "github", KnowledgeSource.WEB],
        top_k=5,
    )

    assert result.id == "doc-1"
    assert result.title == "SPI Guide"
    assert result.content == "Technical content"
    assert result.source is KnowledgeSource.LOCAL
    assert result.score == 2.0
    assert query.query == "SPI layout"
    assert query.sources == [
        KnowledgeSource.LOCAL,
        KnowledgeSource.GITHUB,
        KnowledgeSource.WEB,
    ]


def test_gateway_models_are_frozen_and_forbid_extra_fields() -> None:
    query = KnowledgeQuery(query="SPI")

    with pytest.raises(ValidationError):
        query.query = "UART"
    with pytest.raises(ValidationError):
        KnowledgeResult(
            id="doc",
            title="Title",
            content="Content",
            source="LOCAL",
            unsupported=True,
        )


@pytest.mark.parametrize("top_k", [0, 101])
def test_knowledge_query_validates_top_k(top_k: int) -> None:
    with pytest.raises(ValidationError):
        KnowledgeQuery(query="SPI", top_k=top_k)


@pytest.mark.parametrize("score", [-1.0, math.inf, -math.inf, math.nan])
def test_knowledge_result_rejects_invalid_scores(score: float) -> None:
    with pytest.raises(ValidationError):
        KnowledgeResult(
            id="doc",
            title="Title",
            content="Content",
            source="LOCAL",
            score=score,
        )
