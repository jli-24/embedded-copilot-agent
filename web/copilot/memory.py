from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class MemoryViewerClient(Protocol):
    def get_memory_candidates(self) -> Mapping[str, Any]: ...

    def approve_memory(
        self,
        *,
        memory_id: str,
        candidate_fingerprint: str,
        reviewer: str,
        decision: str,
        reviewed_at: str,
    ) -> Mapping[str, Any]: ...


class MemoryViewer:
    """Safe, presentation-only view of memory candidate projections."""

    __slots__ = ("_client",)

    def __init__(self, client: MemoryViewerClient) -> None:
        self._client = client

    def candidates(self) -> tuple[dict[str, object], ...]:
        payload = self._client.get_memory_candidates()
        raw = payload.get("candidates", ())
        if not isinstance(raw, (tuple, list)):
            return ()
        result: list[dict[str, object]] = []
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            result.append(
                {
                    "memory_id": item.get("memory_id", ""),
                    "memory_type": item.get("memory_type", ""),
                    "source_reference": item.get("source_reference", ""),
                    "confidence": item.get("confidence", 0.0),
                    "review_status": item.get("review_status", ""),
                    "fingerprint": item.get("fingerprint", ""),
                }
            )
        return tuple(result)

    def approve(
        self,
        *,
        memory_id: str,
        candidate_fingerprint: str,
        reviewer: str,
        reviewed_at: str,
    ) -> Mapping[str, Any]:
        return self._client.approve_memory(
            memory_id=memory_id,
            candidate_fingerprint=candidate_fingerprint,
            reviewer=reviewer,
            decision="APPROVED",
            reviewed_at=reviewed_at,
        )

