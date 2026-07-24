from __future__ import annotations

import copy
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from embedded_copilot.firmware.knowledge.models import FirmwareDocument
from embedded_copilot.firmware.knowledge.retriever import FirmwareKnowledgeRetriever
from embedded_copilot.hardware.knowledge.models import HardwareDocument
from embedded_copilot.hardware.knowledge.retriever import HardwareKnowledgeRetriever
from embedded_copilot.knowledge.document_loader import LocalDocumentLoader
from embedded_copilot.knowledge.exceptions import (
    KnowledgeProviderError,
    ProviderError,
    ProviderInvalidResult,
    ProviderUnavailable,
)
from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.pcb.knowledge.models import PCBRuleDocument
from embedded_copilot.pcb.knowledge.retriever import PCBKnowledgeRetriever


_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_+.-]*")
_DOMAINS = {"firmware", "hardware", "pcb", "debug"}


class DocumentLoader(Protocol):
    def load(self, root: Path) -> list[KnowledgeResult]: ...


class LocalKnowledgeProvider:
    """Generate local candidates from a snapshot or legacy domain retrievers."""

    provider_name = "local"
    supported_sources = (KnowledgeSource.LOCAL,)

    def __init__(
        self,
        *,
        knowledge_root: str | Path | None = None,
        loader: DocumentLoader | None = None,
        firmware_retriever: FirmwareKnowledgeRetriever | None = None,
        hardware_retriever: HardwareKnowledgeRetriever | None = None,
        pcb_retriever: PCBKnowledgeRetriever | None = None,
    ) -> None:
        legacy_inputs = (
            firmware_retriever,
            hardware_retriever,
            pcb_retriever,
        )
        if knowledge_root is not None:
            if any(item is not None for item in legacy_inputs):
                raise ProviderInvalidResult(
                    "local provider configuration is invalid"
                )
            self._snapshot_mode = True
            self._firmware_retriever = None
            self._hardware_retriever = None
            self._pcb_retriever = None
            active_loader = loader if loader is not None else LocalDocumentLoader()
            self._snapshot = self._load_snapshot(
                active_loader,
                Path(knowledge_root),
            )
            return
        if loader is not None:
            raise ProviderInvalidResult("local provider configuration is invalid")
        self._snapshot_mode = False
        self._snapshot: tuple[KnowledgeResult, ...] = ()
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
        if self._snapshot_mode:
            raise ProviderInvalidResult("filesystem snapshot is read-only")
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
            assert self._firmware_retriever is not None
            assert self._hardware_retriever is not None
            assert self._pcb_retriever is not None
            if firmware:
                self._firmware_retriever.add_documents(firmware)
            if hardware:
                self._hardware_retriever.add_documents(hardware)
            if pcb:
                self._pcb_retriever.add_documents(pcb)
        except KnowledgeProviderError:
            raise
        except Exception as exc:
            raise KnowledgeProviderError("local document ingestion failed") from exc

    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        if self._snapshot_mode:
            return self._search_snapshot(query)
        try:
            results: list[KnowledgeResult] = []
            assert self._firmware_retriever is not None
            assert self._hardware_retriever is not None
            assert self._pcb_retriever is not None
            for domain, retriever, document_type in (
                ("firmware", self._firmware_retriever, FirmwareDocument),
                ("hardware", self._hardware_retriever, HardwareDocument),
                ("pcb", self._pcb_retriever, PCBRuleDocument),
            ):
                for document in retriever.search(query.query):
                    if not isinstance(document, document_type):
                        raise TypeError("local retriever returned an invalid document")
                    results.append(_map_document(domain, document))
            return results
        except KnowledgeProviderError:
            raise
        except Exception as exc:
            raise KnowledgeProviderError("local knowledge search failed") from exc

    @staticmethod
    def _load_snapshot(
        loader: DocumentLoader,
        root: Path,
    ) -> tuple[KnowledgeResult, ...]:
        try:
            raw_documents = loader.load(root)
            if not isinstance(raw_documents, list):
                raise TypeError("local loader result must be a list")
            snapshot: list[KnowledgeResult] = []
            for document in raw_documents:
                if not isinstance(document, KnowledgeResult):
                    raise TypeError("local loader returned an invalid document")
                validated = KnowledgeResult.model_validate(
                    copy.deepcopy(document.model_dump(mode="python"))
                )
                if validated.source is not KnowledgeSource.LOCAL:
                    raise ValueError("local loader returned a non-local source")
                domain = validated.metadata.get("domain")
                category = validated.metadata.get("category")
                if domain not in _DOMAINS or not isinstance(category, str) or not category:
                    raise ValueError("local loader metadata is invalid")
                snapshot.append(validated)
            return tuple(snapshot)
        except ProviderUnavailable as exc:
            raise ProviderUnavailable(
                "local knowledge root is unavailable"
            ) from exc
        except ProviderInvalidResult as exc:
            raise ProviderInvalidResult(
                "local knowledge snapshot is invalid"
            ) from exc
        except ProviderError as exc:
            raise ProviderInvalidResult(
                "local knowledge snapshot is invalid"
            ) from exc
        except OSError as exc:
            raise ProviderUnavailable("local knowledge root is unavailable") from exc
        except Exception as exc:
            raise ProviderInvalidResult(
                "local knowledge snapshot is invalid"
            ) from exc

    def _search_snapshot(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        query_tokens = _tokens(query.query)
        results: list[KnowledgeResult] = []
        for document in self._snapshot:
            searchable = " ".join(
                (
                    document.id,
                    document.title,
                    document.content,
                    str(document.metadata.get("category", "")),
                    str(document.metadata.get("domain", "")),
                )
            )
            document_tokens = _tokens(searchable)
            matched = query_tokens.intersection(document_tokens)
            if not matched:
                continue
            score = (
                document.score
                if document.score is not None
                else len(matched) / len(query_tokens)
            )
            results.append(
                KnowledgeResult.model_validate(
                    {
                        **copy.deepcopy(document.model_dump(mode="python")),
                        "score": score,
                    }
                )
            )
        return results


def _tokens(value: str) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN.finditer(value)}


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
