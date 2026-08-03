from __future__ import annotations

import copy
import hashlib

from .contracts import (
    MemoryCandidate,
    MemoryReviewStatus,
    VersionMemoryInput,
    _fingerprint_material,
)
from .classifier import classify_memory


def _memory_id(source_fingerprint: str) -> str:
    return "memory-" + hashlib.sha256(source_fingerprint.encode("utf-8")).hexdigest()[:32]


def project_candidate(value: VersionMemoryInput) -> MemoryCandidate:
    if type(value) is not VersionMemoryInput:
        raise TypeError("version memory input must be a typed projection")
    checked = VersionMemoryInput.model_validate(copy.deepcopy(value))
    material = {
        "memory_id": _memory_id(checked.source.source_fingerprint),
        "memory_type": classify_memory(checked),
        "source": checked.source,
        "title": checked.title,
        "tags": checked.tags,
        "summary": checked.summary,
        "evidence_references": checked.evidence_references,
        "confidence": checked.confidence,
        "review_status": MemoryReviewStatus.REVIEW_REQUIRED,
    }
    candidate = MemoryCandidate.model_construct(
        **material, fingerprint="sha256:" + "0" * 64
    )
    return MemoryCandidate.model_validate(
        {**material, "fingerprint": _fingerprint_material(candidate)}
    )
