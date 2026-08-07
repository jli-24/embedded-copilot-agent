from __future__ import annotations

import copy
import hashlib

from .contracts import (
    MemoryCandidate,
    MemoryReviewStatus,
    MemorySourceKind,
    MemorySourceProjection,
    MemoryType,
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


def project_conversation_candidate(value):
    from embedded_copilot.conversation_memory import ConversationMemoryCandidate

    if type(value) is not ConversationMemoryCandidate:
        raise TypeError("conversation memory candidate must be a typed projection")
    checked = ConversationMemoryCandidate.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )
    memory_type = {
        "DECISION": MemoryType.DECISION,
        "ARCHITECTURE": MemoryType.ARCHITECTURE,
        "REQUIREMENT": MemoryType.REQUIREMENT,
        "DEBUG_EXPERIENCE": MemoryType.DEBUG_ANALYSIS_RESULT,
        "OPTIMIZATION": MemoryType.OPTIMIZATION_RESULT,
        "VALIDATION": MemoryType.HIL_VALIDATION_RESULT,
    }[checked.memory_type.value]
    source_projection = MemorySourceProjection(
        source_type=MemorySourceKind.CONVERSATION_SUMMARY,
        source_id=checked.project_id,
        source_reference=(
            checked.related_reference or f"conversation:{checked.source_session}"
        ),
        source_fingerprint=checked.fingerprint,
        observed_at=checked.captured_at,
    )
    return project_candidate(
        VersionMemoryInput(
            source=source_projection,
            summary=checked.decision[:512],
            memory_type=memory_type,
            title=f"Decision rationale: {checked.reason}"[:512],
            evidence_references=(checked.related_reference,)
            if checked.related_reference is not None
            else (),
            confidence=checked.confidence,
        )
    )


__all__ = ["project_candidate", "project_conversation_candidate"]
