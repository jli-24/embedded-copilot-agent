from __future__ import annotations

from embedded_copilot.debug.models import DebugEvidence
from embedded_copilot.firmware.knowledge.models import FirmwareDocument
from embedded_copilot.hardware.knowledge.models import HardwareDocument
from embedded_copilot.knowledge.models import KnowledgeResult, KnowledgeSource
from embedded_copilot.pcb.knowledge.models import PCBRuleDocument
from embedded_copilot.supervisor.knowledge_adapters import (
    adapt_debug_evidence,
    adapt_firmware_documents,
    adapt_hardware_documents,
    adapt_pcb_documents,
    knowledge_provenance,
)


def _result(
    identifier: str,
    *,
    domains: list[str] | None = None,
) -> KnowledgeResult:
    metadata: dict[str, object] = {
        "category": "camera",
        "manufacturer": "Synthetic Vendor",
        "chip": "ESP32",
        "framework": "ESP-IDF",
    }
    if domains is not None:
        metadata["domains"] = domains
    return KnowledgeResult(
        id=identifier,
        title=f"{identifier} title",
        content=f"{identifier} synthetic body",
        source=KnowledgeSource.LOCAL,
        score=0.9,
        metadata=metadata,
    )


def test_adapters_filter_domains_and_preserve_gateway_order() -> None:
    shared = _result("shared")
    firmware = _result("firmware", domains=["firmware"])
    hardware = _result("hardware", domains=["hardware"])
    results = [hardware, shared, firmware]

    firmware_documents = adapt_firmware_documents(results)
    hardware_documents = adapt_hardware_documents(results)
    pcb_documents = adapt_pcb_documents(results)
    debug_evidence = adapt_debug_evidence(results)

    assert all(isinstance(item, FirmwareDocument) for item in firmware_documents)
    assert [item.id for item in firmware_documents] == ["shared", "firmware"]
    assert all(isinstance(item, HardwareDocument) for item in hardware_documents)
    assert [item.id for item in hardware_documents] == ["hardware", "shared"]
    assert all(isinstance(item, PCBRuleDocument) for item in pcb_documents)
    assert [item.id for item in pcb_documents] == ["shared"]
    assert all(isinstance(item, DebugEvidence) for item in debug_evidence)
    assert [item.metadata["id"] for item in debug_evidence] == ["shared"]


def test_adapter_provenance_excludes_content_and_provider_metadata() -> None:
    result = _result("camera")

    provenance = knowledge_provenance([result], domain="hardware")
    serialized = str(provenance)

    assert provenance == [
        {
            "id": "camera",
            "title": "camera title",
            "source": "LOCAL",
            "category": "camera",
            "score": 0.9,
        }
    ]
    assert "synthetic body" not in serialized
    assert "manufacturer" not in serialized
    assert "framework" not in serialized


def test_adapters_sanitize_paths_and_urls_with_query_parameters() -> None:
    result = KnowledgeResult(
        id="C:\\private\\datasheet.pdf",
        title="https://example.test/doc?token=private",
        content="Synthetic body allowed only in the domain document",
        source=KnowledgeSource.LOCAL,
        score=0.9,
        metadata={
            "category": "https://example.test/category?secret=private",
            "manufacturer": "https://example.test/vendor?key=private",
            "chip": "https://example.test/chip?credential=private",
            "framework": "https://example.test/sdk?token=private",
        },
    )

    document = adapt_firmware_documents([result])[0]
    provenance = knowledge_provenance([result], domain="firmware")[0]
    serialized = str((document.model_dump(mode="json"), provenance))

    assert document.id == "knowledge-result"
    assert document.title == "Knowledge result"
    assert document.platform == "Generic"
    assert document.framework == "Generic"
    assert provenance["category"] == "firmware"
    assert "private" not in serialized
    assert "token=" not in serialized
