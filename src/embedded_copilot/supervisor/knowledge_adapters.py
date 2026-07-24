from __future__ import annotations

import copy
import re
from collections.abc import Sequence

from embedded_copilot.debug.models import DebugEvidence
from embedded_copilot.firmware.knowledge.models import FirmwareDocument
from embedded_copilot.hardware.knowledge.models import HardwareDocument
from embedded_copilot.knowledge.models import KnowledgeResult
from embedded_copilot.pcb.knowledge.models import PCBRuleDocument


_UNSAFE_TEXT = re.compile(
    r"^(?:[A-Za-z]:[\\/]|\\\\|/|file://|https?://[^\s]+\?)",
    re.I,
)


def _safe_text(value: object, fallback: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return fallback
    candidate = value.strip()
    return fallback if _UNSAFE_TEXT.match(candidate) else candidate


def _text(metadata: dict[str, object], key: str, fallback: str) -> str:
    return _safe_text(metadata.get(key), fallback)


def _domains(result: KnowledgeResult) -> tuple[str, ...] | None:
    raw = result.metadata.get("domains", result.metadata.get("domain"))
    if isinstance(raw, str) and raw.strip():
        return (raw.strip().casefold(),)
    if isinstance(raw, list) and all(
        isinstance(item, str) and item.strip() for item in raw
    ):
        return tuple(item.strip().casefold() for item in raw)
    return None


def _for_domain(
    results: Sequence[KnowledgeResult],
    domain: str,
) -> list[KnowledgeResult]:
    return [
        result
        for result in results
        if (scopes := _domains(result)) is None or domain in scopes
    ]


def adapt_firmware_documents(
    results: Sequence[KnowledgeResult],
) -> list[FirmwareDocument]:
    return [
        FirmwareDocument(
            id=_safe_text(result.id, "knowledge-result"),
            title=_safe_text(result.title, "Knowledge result"),
            platform=_text(result.metadata, "chip", "Generic"),
            framework=_text(result.metadata, "framework", "Generic"),
            content=result.content,
            metadata=_document_metadata(result),
        )
        for result in _for_domain(results, "firmware")
    ]


def adapt_hardware_documents(
    results: Sequence[KnowledgeResult],
) -> list[HardwareDocument]:
    return [
        HardwareDocument(
            id=_safe_text(result.id, "knowledge-result"),
            title=_safe_text(result.title, "Knowledge result"),
            category=_text(result.metadata, "category", "general"),
            vendor=_text(result.metadata, "manufacturer", "unspecified"),
            content=result.content,
            metadata=_document_metadata(result),
        )
        for result in _for_domain(results, "hardware")
    ]


def adapt_pcb_documents(
    results: Sequence[KnowledgeResult],
) -> list[PCBRuleDocument]:
    return [
        PCBRuleDocument(
            id=_safe_text(result.id, "knowledge-result"),
            title=_safe_text(result.title, "Knowledge result"),
            category=_text(result.metadata, "category", "general"),
            content=result.content,
            metadata=_document_metadata(result),
        )
        for result in _for_domain(results, "pcb")
    ]


def adapt_debug_evidence(
    results: Sequence[KnowledgeResult],
) -> list[DebugEvidence]:
    return [
        DebugEvidence(
            source=(
                f"{result.source.value}:"
                f"{_safe_text(result.id, 'knowledge-result')}"
            ),
            content=result.content,
            category=_text(result.metadata, "category", "debug"),
            metadata={
                "id": _safe_text(result.id, "knowledge-result"),
                "title": _safe_text(result.title, "Knowledge result"),
                "source": result.source.value,
                "score": result.score,
            },
        )
        for result in _for_domain(results, "debug")
    ]


def knowledge_provenance(
    results: Sequence[KnowledgeResult],
    *,
    domain: str,
) -> list[dict[str, object]]:
    return [
        {
            "id": _safe_text(result.id, "knowledge-result"),
            "title": _safe_text(result.title, "Knowledge result"),
            "source": result.source.value,
            "category": _text(result.metadata, "category", domain),
            "score": result.score,
        }
        for result in _for_domain(results, domain)
    ]


def knowledge_categories(results: Sequence[KnowledgeResult]) -> list[str]:
    categories: list[str] = []
    seen: set[str] = set()
    for result in results:
        category = _text(result.metadata, "category", "")
        key = category.casefold()
        if category and key not in seen:
            seen.add(key)
            categories.append(category)
    return categories


def _document_metadata(result: KnowledgeResult) -> dict[str, object]:
    return copy.deepcopy(
        {
            "knowledge_id": _safe_text(result.id, "knowledge-result"),
            "knowledge_source": result.source.value,
            "knowledge_score": result.score,
        }
    )
