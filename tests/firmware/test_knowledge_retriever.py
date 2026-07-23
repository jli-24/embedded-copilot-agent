from embedded_copilot.firmware.knowledge.models import FirmwareDocument
from embedded_copilot.firmware.knowledge.retriever import FirmwareKnowledgeRetriever
from embedded_copilot.knowledge.base import KnowledgeRetriever


def _document(
    document_id: str,
    title: str,
    content: str,
    *,
    platform: str = "ESP32",
    framework: str = "ESP-IDF",
) -> FirmwareDocument:
    return FirmwareDocument(
        id=document_id,
        title=title,
        platform=platform,
        framework=framework,
        content=content,
        metadata={"source": f"{document_id}.md"},
    )


def test_retriever_implements_protocol_and_retrieve_alias() -> None:
    retriever = FirmwareKnowledgeRetriever(
        [_document("wifi", "WiFi Guide", "ESP32 WiFi connection")]
    )

    assert isinstance(retriever, KnowledgeRetriever)
    assert retriever.search("ESP32 WiFi") == retriever.retrieve("ESP32 WiFi")


def test_retriever_ranks_matches_and_adds_non_probability_score() -> None:
    retriever = FirmwareKnowledgeRetriever(
        [
            _document("gpio", "GPIO", "ESP32 pin notes"),
            _document("wifi", "WiFi", "ESP32 WiFi upload notes"),
            _document("stm32", "UART", "STM32 HAL UART", platform="STM32", framework="HAL"),
        ],
        top_k=2,
    )

    results = retriever.retrieve("ESP32 WiFi upload")

    assert [item.id for item in results] == ["wifi", "gpio"]
    assert results[0].metadata["retrieval_score"] == 3
    assert results[0].metadata["retrieval_score_kind"] == "keyword_overlap"


def test_retriever_returns_empty_for_no_keywords() -> None:
    retriever = FirmwareKnowledgeRetriever(
        [_document("wifi", "WiFi", "ESP32 wireless")]
    )

    assert retriever.retrieve("unrelated camera") == []
    assert retriever.retrieve("   ") == []


def test_retriever_upserts_duplicate_ids_without_reordering() -> None:
    retriever = FirmwareKnowledgeRetriever(
        [
            _document("one", "First", "GPIO"),
            _document("two", "Second", "UART"),
        ]
    )
    retriever.add_documents([_document("one", "Updated", "Camera WiFi")])

    results = retriever.retrieve("Camera")

    assert [item.id for item in results] == ["one"]
    assert results[0].title == "Updated"
