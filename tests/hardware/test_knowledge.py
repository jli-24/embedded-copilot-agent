import pytest
from pydantic import ValidationError

from embedded_copilot.hardware.knowledge.models import HardwareDocument
from embedded_copilot.hardware.knowledge.retriever import HardwareKnowledgeRetriever
from embedded_copilot.knowledge.base import KnowledgeRetriever


def _document(
    document_id: str,
    title: str,
    content: str,
    *,
    category: str = "general",
    vendor: str = "Generic",
) -> HardwareDocument:
    return HardwareDocument(
        id=document_id,
        title=title,
        category=category,
        vendor=vendor,
        content=content,
        metadata={"license": "original-test-seed"},
    )


def test_hardware_document_strips_fields_and_forbids_extra() -> None:
    document = HardwareDocument(
        id=" doc ",
        title=" Camera Guide ",
        category=" camera ",
        vendor=" Vendor ",
        content=" mock knowledge ",
    )

    assert document.id == "doc"
    assert document.title == "Camera Guide"
    with pytest.raises(ValidationError):
        HardwareDocument(
            id="doc",
            title="Guide",
            category="camera",
            vendor="Vendor",
            content="content",
            extra=True,
        )


def test_retriever_implements_protocol_and_retrieve_alias() -> None:
    retriever = HardwareKnowledgeRetriever(
        [_document("camera", "Camera Guide", "ESP32 camera module")]
    )

    assert isinstance(retriever, KnowledgeRetriever)
    assert retriever.search("ESP32 camera") == retriever.retrieve("ESP32 camera")


def test_retriever_ranks_top_k_and_adds_non_probability_score() -> None:
    retriever = HardwareKnowledgeRetriever(
        [
            _document("gpio", "GPIO", "ESP32 connector"),
            _document("camera", "Camera", "ESP32 camera module SPI"),
            _document("uart", "UART", "STM32 UART", category="interface"),
        ],
        top_k=2,
    )

    results = retriever.retrieve("ESP32 camera SPI")

    assert [item.id for item in results] == ["camera", "gpio"]
    assert results[0].metadata["retrieval_score"] == 3
    assert results[0].metadata["retrieval_score_kind"] == "keyword_overlap"


def test_retriever_returns_empty_and_upserts_without_reordering() -> None:
    retriever = HardwareKnowledgeRetriever(
        [
            _document("one", "First", "GPIO"),
            _document("two", "Second", "UART"),
        ]
    )
    retriever.add_documents([_document("one", "Updated", "Camera WiFi")])

    assert retriever.retrieve("unrelated") == []
    assert [item.id for item in retriever.retrieve("Camera")] == ["one"]
    assert retriever.retrieve("Camera")[0].title == "Updated"


def test_retriever_preserves_insertion_order_for_ties() -> None:
    retriever = HardwareKnowledgeRetriever(
        [
            _document("first", "First", "Camera"),
            _document("second", "Second", "Camera"),
        ]
    )

    assert [item.id for item in retriever.retrieve("Camera")] == [
        "first",
        "second",
    ]
