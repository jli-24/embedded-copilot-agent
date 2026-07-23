from __future__ import annotations

from collections.abc import Sequence

from embedded_copilot.firmware.knowledge.models import FirmwareDocument
from embedded_copilot.firmware.knowledge.retriever import FirmwareKnowledgeRetriever
from embedded_copilot.hardware.knowledge.models import HardwareDocument
from embedded_copilot.hardware.knowledge.retriever import HardwareKnowledgeRetriever
from embedded_copilot.knowledge.exceptions import KnowledgeProviderError
from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.pcb.knowledge.models import PCBRuleDocument
from embedded_copilot.pcb.knowledge.retriever import PCBKnowledgeRetriever


class LocalKnowledgeProvider:
    """Read-only unified search adapter for the existing domain retrievers."""

    provider_name = "local"
    supported_sources = (KnowledgeSource.LOCAL,)

    def __init__(
        self,
        *,
        firmware_retriever: FirmwareKnowledgeRetriever | None = None,
        hardware_retriever: HardwareKnowledgeRetriever | None = None,
        pcb_retriever: PCBKnowledgeRetriever | None = None,
    ) -> None:
        self._firmware_retriever = (
            firmware_retriever
            if firmware_retriever is not None
            else FirmwareKnowledgeRetriever()
        )
        self._hardware_retriever = (
            hardware_retriever
            if hardware_retriever is not None
            else HardwareKnowledgeRetriever()
        )
        self._pcb_retriever = (
            pcb_retriever if pcb_retriever is not None else PCBKnowledgeRetriever()
        )

    def add_documents(self, documents: Sequence[object]) -> None:
        firmware: list[FirmwareDocument] = []
        hardware: list[HardwareDocument] = []
        pcb: list[PCBRuleDocument] = []
        try:
            for document in documents:
                if isinstance(document, FirmwareDocument):
                    firmware.append(document)
                elif isinstance(document, HardwareDocument):
                    hardware.append(document)
                elif isinstance(document, PCBRuleDocument):
                    pcb.append(document)
                else:
                    raise TypeError("unsupported local knowledge document")
            if firmware:
                self._firmware_retriever.add_documents(firmware)
            if hardware:
                self._hardware_retriever.add_documents(hardware)
            if pcb:
                self._pcb_retriever.add_documents(pcb)
        except Exception as exc:
            raise KnowledgeProviderError("local document ingestion failed") from exc

    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        try:
            ranked: list[tuple[KnowledgeResult, int]] = []
            position = 0
            for domain, retriever, document_type in (
                ("firmware", self._firmware_retriever, FirmwareDocument),
                ("hardware", self._hardware_retriever, HardwareDocument),
                ("pcb", self._pcb_retriever, PCBRuleDocument),
            ):
                for document in retriever.search(query.query):
                    if not isinstance(document, document_type):
                        raise TypeError("local retriever returned an invalid document")
                    ranked.append(
                        (
                            _map_document(domain, document),
                            position,
                        )
                    )
                    position += 1
            ranked.sort(key=lambda item: _ranking_key(item[0], item[1]))
            return [result for result, _ in ranked[: query.top_k]]
        except KnowledgeProviderError:
            raise
        except Exception as exc:
            raise KnowledgeProviderError("local knowledge search failed") from exc


def _map_document(
    domain: str,
    document: FirmwareDocument | HardwareDocument | PCBRuleDocument,
) -> KnowledgeResult:
    raw_score = document.metadata.get("retrieval_score")
    score: float | None
    if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
        score = None
    else:
        score = float(raw_score)

    if isinstance(document, HardwareDocument):
        category = document.category
    elif isinstance(document, PCBRuleDocument):
        category = document.category
    else:
        category = "firmware"

    return KnowledgeResult(
        id=f"{domain}:{document.id}",
        title=document.title,
        content=document.content,
        source=KnowledgeSource.LOCAL,
        score=score,
        metadata={
            "document_id": document.id,
            "category": category,
            "domain": domain,
            "retrieval_score": score,
        },
    )


def _ranking_key(result: KnowledgeResult, position: int) -> tuple[bool, float, int]:
    return (
        result.score is None,
        -(result.score if result.score is not None else 0.0),
        position,
    )
