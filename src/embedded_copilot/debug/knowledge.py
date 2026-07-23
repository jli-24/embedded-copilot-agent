from __future__ import annotations

import copy
import re
from collections.abc import Iterable

from embedded_copilot.debug.exceptions import DebugKnowledgeError
from embedded_copilot.debug.models import DebugEvidence, DebugRequest
from embedded_copilot.knowledge.models import KnowledgeResult


_DIAGNOSTIC_KEYWORDS = (
    "reset",
    "watchdog",
    "reboot",
    "exception",
    "abort",
    "stack overflow",
    "heap",
    "malloc",
    "allocation",
    "missing include",
    "undefined reference",
    "type mismatch",
    "hardfault",
    "busfault",
    "memmanage",
    "null",
    "uart",
    "framing",
    "overrun",
    "spi",
    "i2c",
    "nack",
    "wifi disconnect",
)
_ABSOLUTE_LOCAL_PATH = re.compile(
    r"(?<![A-Za-z])[A-Za-z]:[\\/]|\\\\|file://|(?:^|:)/(?!/)",
    re.IGNORECASE,
)


def _safe_query(request: DebugRequest) -> str:
    searchable = " ".join([request.input, *request.logs]).casefold()
    keywords = [keyword for keyword in _DIAGNOSTIC_KEYWORDS if keyword in searchable]
    parts = [part for part in (request.platform, request.error_type) if part]
    return " ".join([*parts, *keywords])


class DebugKnowledgeRetriever:
    """Adapt an explicitly injected string-query backend to debug evidence."""

    def __init__(self, backend: object | None = None) -> None:
        self._backend = backend

    def retrieve(self, request: DebugRequest) -> list[DebugEvidence]:
        if self._backend is None:
            return []
        try:
            search = getattr(self._backend, "search", None)
            operation = (
                search
                if callable(search)
                else getattr(self._backend, "retrieve", None)
            )
            if not callable(operation):
                raise DebugKnowledgeError(
                    "debug knowledge backend must provide search or retrieve"
                )
            raw_results = operation(_safe_query(request))
            if isinstance(raw_results, (str, bytes)) or not isinstance(
                raw_results, Iterable
            ):
                raise TypeError("knowledge results must be iterable")
            evidence: list[DebugEvidence] = []
            for raw_result in raw_results:
                if isinstance(raw_result, KnowledgeResult):
                    payload = raw_result.model_dump(mode="python")
                else:
                    payload = raw_result
                result = KnowledgeResult.model_validate(copy.deepcopy(payload))
                category = result.metadata.get("category", "debug")
                if not isinstance(category, str) or not category.strip():
                    category = "debug"
                item = DebugEvidence(
                    source=f"{result.source.value}:{result.id}",
                    content=result.content,
                    category=category,
                    metadata={
                        "id": result.id,
                        "title": result.title,
                        "source": result.source.value,
                        "score": result.score,
                        "knowledge_metadata": copy.deepcopy(result.metadata),
                    },
                )
                debug_evidence_provenance(item)
                evidence.append(item)
            return evidence
        except DebugKnowledgeError:
            raise
        except Exception as exc:
            raise DebugKnowledgeError("debug knowledge retrieval failed") from exc


def debug_evidence_provenance(evidence: DebugEvidence) -> dict[str, object]:
    """Return allowlisted provenance without knowledge content."""

    metadata = evidence.metadata
    provenance = {
        "id": metadata.get("id"),
        "title": metadata.get("title"),
        "source": metadata.get("source"),
        "category": evidence.category,
        "score": metadata.get("score"),
    }
    for field in ("id", "title", "source", "category"):
        value = provenance[field]
        if not isinstance(value, str) or not value.strip():
            raise DebugKnowledgeError("debug knowledge retrieval failed")
    score = provenance["score"]
    if score is not None and (
        not isinstance(score, (int, float)) or isinstance(score, bool)
    ):
        raise DebugKnowledgeError("debug knowledge retrieval failed")
    for value in [evidence.source, *provenance.values()]:
        if isinstance(value, str) and _ABSOLUTE_LOCAL_PATH.search(value.strip()):
            raise DebugKnowledgeError("debug knowledge retrieval failed")
    return provenance
