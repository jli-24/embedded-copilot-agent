from __future__ import annotations

from embedded_copilot.hardware_design.models import (
    _v22_canonical,
    _v22_fingerprint,
    _v22_id,
    _v22_text,
)


def review_id(project_id: str, category: str, index: int) -> str:
    return _v22_id(f"review:{project_id}:{category.lower()}:{index}", field="review_id")


def review_summary(value: object) -> str:
    return _v22_text(value, field="summary", maximum=512)


def review_evidence(value: object) -> str:
    return _v22_id(value, field="evidence_reference")


__all__ = [
    "_v22_canonical",
    "_v22_fingerprint",
    "review_evidence",
    "review_id",
    "review_summary",
]
