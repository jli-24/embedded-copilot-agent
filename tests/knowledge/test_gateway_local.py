import pytest

from embedded_copilot.firmware.knowledge import (
    FirmwareDocument,
    FirmwareKnowledgeRetriever,
)
from embedded_copilot.hardware.knowledge import (
    HardwareDocument,
    HardwareKnowledgeRetriever,
)
from embedded_copilot.knowledge.exceptions import KnowledgeProviderError
from embedded_copilot.knowledge.local import LocalKnowledgeProvider
from embedded_copilot.knowledge.models import KnowledgeQuery, KnowledgeSource
from embedded_copilot.knowledge.providers import KnowledgeProvider
from embedded_copilot.pcb.knowledge import PCBKnowledgeRetriever, PCBRuleDocument


def _firmware() -> FirmwareDocument:
    return FirmwareDocument(
        id="fw-spi",
        title="SPI Firmware",
        platform="ESP32",
        framework="ESP-IDF",
        content="SPI driver guidance",
        metadata={"private_note": "discarded"},
    )


def _hardware() -> HardwareDocument:
    return HardwareDocument(
        id="hw-spi",
        title="SPI Hardware",
        category="communication",
        vendor="Example",
        content="SPI layout guidance",
        metadata={"private_note": "discarded"},
    )


def _pcb() -> PCBRuleDocument:
    return PCBRuleDocument(
        id="pcb-spi",
        title="SPI PCB",
        category="layout",
        content="SPI PCB review guidance",
        metadata={"private_note": "discarded"},
    )


def _provider() -> LocalKnowledgeProvider:
    return LocalKnowledgeProvider(
        firmware_retriever=FirmwareKnowledgeRetriever([_firmware()]),
        hardware_retriever=HardwareKnowledgeRetriever([_hardware()]),
        pcb_retriever=PCBKnowledgeRetriever([_pcb()]),
    )


def test_local_provider_is_protocol_compatible_and_empty_by_default() -> None:
    provider = LocalKnowledgeProvider()

    assert isinstance(provider, KnowledgeProvider)
    assert provider.provider_name == "local"
    assert provider.supported_sources == (KnowledgeSource.LOCAL,)
    assert provider.search(KnowledgeQuery(query="SPI")) == []


def test_local_provider_maps_all_domains_with_safe_namespaced_metadata() -> None:
    query = KnowledgeQuery(
        query="SPI",
        top_k=10,
        metadata={"filters": {"chip": "ESP32"}},
    )
    original_query = query.model_dump(mode="json")
    firmware = _firmware()
    hardware = _hardware()
    pcb = _pcb()
    original_documents = [
        firmware.model_dump(mode="json"),
        hardware.model_dump(mode="json"),
        pcb.model_dump(mode="json"),
    ]
    provider = LocalKnowledgeProvider(
        firmware_retriever=FirmwareKnowledgeRetriever([firmware]),
        hardware_retriever=HardwareKnowledgeRetriever([hardware]),
        pcb_retriever=PCBKnowledgeRetriever([pcb]),
    )

    results = provider.search(query)

    assert [result.id for result in results] == [
        "firmware:fw-spi",
        "hardware:hw-spi",
        "pcb:pcb-spi",
    ]
    assert all(result.source is KnowledgeSource.LOCAL for result in results)
    assert results[0].metadata == {
        "document_id": "fw-spi",
        "category": "firmware",
        "domain": "firmware",
        "retrieval_score": 1,
    }
    assert results[1].metadata["category"] == "communication"
    assert results[2].metadata["category"] == "layout"
    assert all("private_note" not in result.metadata for result in results)
    assert query.model_dump(mode="json") == original_query
    assert [
        firmware.model_dump(mode="json"),
        hardware.model_dump(mode="json"),
        pcb.model_dump(mode="json"),
    ] == original_documents


def test_legacy_local_provider_returns_all_candidates_in_stable_order() -> None:
    results = _provider().search(KnowledgeQuery(query="SPI", top_k=2))

    assert [result.id for result in results] == [
        "firmware:fw-spi",
        "hardware:hw-spi",
        "pcb:pcb-spi",
    ]


class _RecordingRetriever:
    def __init__(self) -> None:
        self.documents: list[object] = []

    def add_documents(self, documents) -> None:
        self.documents.extend(documents)

    def search(self, query: str):
        return []


def test_local_provider_dispatches_mixed_documents_by_type() -> None:
    firmware = _RecordingRetriever()
    hardware = _RecordingRetriever()
    pcb = _RecordingRetriever()
    provider = LocalKnowledgeProvider(
        firmware_retriever=firmware,
        hardware_retriever=hardware,
        pcb_retriever=pcb,
    )

    provider.add_documents([_firmware(), _hardware(), _pcb()])

    assert [type(item) for item in firmware.documents] == [FirmwareDocument]
    assert [type(item) for item in hardware.documents] == [HardwareDocument]
    assert [type(item) for item in pcb.documents] == [PCBRuleDocument]


def test_local_provider_prevalidates_unknown_documents_before_writing() -> None:
    firmware = _RecordingRetriever()
    hardware = _RecordingRetriever()
    pcb = _RecordingRetriever()
    provider = LocalKnowledgeProvider(
        firmware_retriever=firmware,
        hardware_retriever=hardware,
        pcb_retriever=pcb,
    )

    with pytest.raises(
        KnowledgeProviderError,
        match="local document ingestion failed",
    ):
        provider.add_documents([_firmware(), object()])

    assert firmware.documents == []
    assert hardware.documents == []
    assert pcb.documents == []


class _UnsafeScoreRetriever:
    def search(self, query: str):
        return [
            _firmware().model_copy(
                update={
                    "metadata": {
                        "retrieval_score": "C:/Users/private/SECRET_SENTINEL"
                    }
                }
            )
        ]

    def add_documents(self, documents) -> None:
        return None


def test_local_provider_maps_non_numeric_score_to_none_without_leaking() -> None:
    provider = LocalKnowledgeProvider(
        firmware_retriever=_UnsafeScoreRetriever(),
        hardware_retriever=_RecordingRetriever(),
        pcb_retriever=_RecordingRetriever(),
    )

    result = provider.search(KnowledgeQuery(query="SPI"))[0]

    assert result.score is None
    assert result.metadata["retrieval_score"] is None
    assert "SECRET_SENTINEL" not in str(result.model_dump())
