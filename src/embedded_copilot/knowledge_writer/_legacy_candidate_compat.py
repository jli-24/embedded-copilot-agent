"""Legacy test compatibility for pre-approval candidate projections.

This adapter is intentionally outside the canonical writer contracts. The
production writer and ``KnowledgeWriterPort`` accept approved projections or
validated markdown artifacts only.
"""

from __future__ import annotations

import copy

from embedded_copilot.memory_automation.contracts import MemoryCandidate

from .contracts import MarkdownArtifact


def artifact_from_candidate(candidate: MemoryCandidate) -> MarkdownArtifact:
    if type(candidate) is not MemoryCandidate:
        raise TypeError("memory candidate must be a typed projection")
    checked = MemoryCandidate.model_validate(copy.deepcopy(candidate))
    if checked.review_status.value != "APPROVED":
        raise ValueError("memory candidate is not approved")
    filename = f"{checked.memory_id}-{checked.memory_type.value.lower()}.md"
    return MarkdownArtifact(
        memory_id=checked.memory_id,
        memory_type=checked.memory_type,
        status="APPROVED",
        layer=checked.layer,
        tags=checked.tags,
        title=checked.title,
        summary=checked.summary,
        evidence_references=checked.evidence_references,
        relative_path=f"docs/knowledge/{filename}",
        candidate_fingerprint=checked.fingerprint,
        decision=checked.summary,
        reason=checked.title,
    )


__all__ = ["artifact_from_candidate"]
