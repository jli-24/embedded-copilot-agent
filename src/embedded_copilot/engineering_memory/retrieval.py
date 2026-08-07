from __future__ import annotations

import copy
import re

from .contracts import (
    ApprovedEngineeringMemory,
    EngineeringMemoryQuery,
    EngineeringMemoryRetrievalResult,
)
from .store import ApprovedEngineeringMemoryStorePort

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{1,63}")


def _tokens(value: str) -> frozenset[str]:
    return frozenset(item.casefold() for item in _TOKEN.findall(value))


def _score(memory: ApprovedEngineeringMemory, query_tokens: frozenset[str]) -> int:
    material = " ".join(
        (memory.summary, memory.decision, memory.reason, *memory.evidence)
    )
    return len(query_tokens & _tokens(material))


class EngineeringMemoryRetrievalService:
    __slots__ = ("_store",)

    def __init__(self, store: ApprovedEngineeringMemoryStorePort) -> None:
        if not isinstance(store, ApprovedEngineeringMemoryStorePort):
            raise TypeError("approved memory store is invalid")
        self._store = store

    def query(self, request: EngineeringMemoryQuery) -> EngineeringMemoryRetrievalResult:
        checked = EngineeringMemoryQuery.model_validate(copy.deepcopy(request))
        query_tokens = _tokens(checked.query)
        memories = tuple(
            item
            for item in self._store.query_records(checked)
            if item.status == "APPROVED"
        )
        ranked = tuple(
            sorted(
                memories,
                key=lambda item: (
                    -_score(item, query_tokens),
                    item.memory_id,
                    item.fingerprint,
                ),
            )[: checked.limit]
        )
        return EngineeringMemoryRetrievalResult.create(
            project_id=checked.project_id,
            memories=tuple(
                ApprovedEngineeringMemory.model_validate(copy.deepcopy(item))
                for item in ranked
            ),
        )


__all__ = ("EngineeringMemoryRetrievalService",)
