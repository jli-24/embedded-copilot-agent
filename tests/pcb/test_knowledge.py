import pytest
from pydantic import ValidationError

from embedded_copilot.knowledge.base import KnowledgeRetriever
from embedded_copilot.pcb.knowledge import PCBKnowledgeRetriever, PCBRuleDocument


def _document(
    document_id: str,
    title: str,
    category: str,
    content: str,
) -> PCBRuleDocument:
    return PCBRuleDocument(
        id=document_id,
        title=title,
        category=category,
        content=content,
        metadata={"license": "test"},
    )


def test_rule_document_strips_fields_and_forbids_extra() -> None:
    document = PCBRuleDocument(
        id=" rule-1 ",
        title=" Layout Guide ",
        category=" communication ",
        content=" Authorized test content. ",
    )

    assert document.id == "rule-1"
    assert document.title == "Layout Guide"
    with pytest.raises(ValidationError):
        PCBRuleDocument(
            id="rule-1",
            title="Layout",
            category="communication",
            content="content",
            extra=True,
        )


def test_retriever_is_protocol_compatible_and_ranks_stably() -> None:
    first = _document("spi", "SPI Layout", "communication", "SPI ground")
    second = _document("power", "Power Guide", "power", "ground")
    third = _document("ground", "Ground Guide", "ground", "ground")
    retriever = PCBKnowledgeRetriever([first, second, third], top_k=2)

    results = list(retriever.search("SPI ground"))

    assert isinstance(retriever, KnowledgeRetriever)
    assert [result.id for result in results] == ["spi", "power"]
    assert results[0].metadata["retrieval_score"] == 2
    assert results[1].metadata["retrieval_score"] == 1


def test_retrieve_alias_filters_zero_scores_and_does_not_mutate_documents() -> None:
    source = _document("spi", "SPI Layout", "communication", "routing")
    retriever = PCBKnowledgeRetriever([source])

    assert retriever.retrieve("unrelated") == []
    result = retriever.retrieve("SPI")[0]
    assert result.metadata["retrieval_score_kind"] == "keyword_overlap"
    assert source.metadata == {"license": "test"}


def test_repeated_document_id_is_idempotently_upserted_in_original_position() -> None:
    retriever = PCBKnowledgeRetriever(
        [
            _document("first", "Old SPI", "communication", "old"),
            _document("second", "Ground", "ground", "ground"),
        ]
    )
    retriever.add_documents(
        [_document("first", "Updated Power", "power", "power ground")]
    )

    results = retriever.retrieve("power ground")

    assert [result.id for result in results] == ["first", "second"]
    assert results[0].title == "Updated Power"


def test_retriever_rejects_non_positive_top_k() -> None:
    with pytest.raises(ValueError, match="positive"):
        PCBKnowledgeRetriever(top_k=0)
