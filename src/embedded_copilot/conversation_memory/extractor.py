from __future__ import annotations

from .contracts import ConversationSnapshot, safe_text
from .models import MemoryType


def extract_fields(
    snapshot: ConversationSnapshot,
    memory_type: MemoryType,
    text: str,
    reference: str | None,
) -> dict[str, object]:
    summary = safe_text(" ".join(text.split())[:2048], field="summary")
    return {
        "summary": summary,
        "decision": summary if memory_type in (MemoryType.DECISION, MemoryType.ARCHITECTURE) else "Not established.",
        "reason": "Deterministic engineering signal extracted from the conversation snapshot.",
        "related_reference": reference,
        "confidence": 0.75 if reference is not None else 0.5,
        "captured_at": snapshot.captured_at,
    }


__all__ = ["extract_fields"]
