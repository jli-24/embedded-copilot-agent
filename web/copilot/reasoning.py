from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class ReasoningViewerClient(Protocol):
    def query_reasoning(
        self,
        *,
        recommendation_id: str,
        mode: str,
        question: str,
    ) -> Mapping[str, Any]: ...


class ReasoningPanel:
    """Presentation-only wrapper for the safe reasoning response."""

    __slots__ = ("_client",)

    def __init__(self, client: ReasoningViewerClient) -> None:
        self._client = client

    def query(
        self,
        *,
        recommendation_id: str,
        mode: str,
        question: str,
    ) -> dict[str, object]:
        payload = self._client.query_reasoning(
            recommendation_id=recommendation_id,
            mode=mode,
            question=question,
        )
        return {
            "summary": payload.get("summary", ""),
            "explanation": payload.get("explanation", ""),
            "tradeoffs": payload.get("tradeoffs", ()),
            "risks": payload.get("risks", ()),
            "references": payload.get("references", ()),
            "confidence": payload.get("confidence", 0.0),
        }


__all__ = ["ReasoningPanel"]
