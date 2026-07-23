from embedded_copilot.firmware.knowledge import FirmwareDocument
from embedded_copilot.knowledge.base import KnowledgeRetriever
from embedded_copilot.knowledge.gateway import (
    KnowledgeGateway,
    KnowledgeGatewayAdapter,
)
from embedded_copilot.knowledge.local import LocalKnowledgeProvider
from embedded_copilot.knowledge.models import KnowledgeSource


def _firmware_document() -> FirmwareDocument:
    return FirmwareDocument(
        id="spi",
        title="SPI Firmware",
        platform="ESP32",
        framework="ESP-IDF",
        content="SPI guidance",
    )


class _MetadataCaptureProvider:
    provider_name = "capture"
    supported_sources = (KnowledgeSource.LOCAL,)

    def __init__(self) -> None:
        self.metadata: list[dict[str, object]] = []

    def search(self, query):
        self.metadata.append(query.model_dump(mode="json")["metadata"])
        return []


def test_gateway_adapter_is_legacy_protocol_compatible_and_searches() -> None:
    local = LocalKnowledgeProvider()
    gateway = KnowledgeGateway([local])
    configuration = {"filters": {"chip": "ESP32"}}
    adapter = KnowledgeGatewayAdapter(
        gateway,
        local,
        sources=[KnowledgeSource.LOCAL, KnowledgeSource.LOCAL],
        top_k=1,
        metadata=configuration,
    )
    original = {"filters": {"chip": "ESP32"}}
    adapter.add_documents([_firmware_document()])

    results = list(adapter.search("SPI"))

    assert isinstance(adapter, KnowledgeRetriever)
    assert [result.id for result in results] == ["firmware:spi"]
    assert len(results) == 1
    assert configuration == original


def test_adapter_copies_configuration_metadata_from_caller() -> None:
    local = LocalKnowledgeProvider()
    capture = _MetadataCaptureProvider()
    configuration = {"filters": {"chip": "ESP32"}}
    adapter = KnowledgeGatewayAdapter(
        KnowledgeGateway([capture]),
        local,
        metadata=configuration,
    )
    configuration["filters"]["chip"] = "STM32"

    assert adapter.search("SPI") == []
    assert capture.metadata == [{"filters": {"chip": "ESP32"}}]
