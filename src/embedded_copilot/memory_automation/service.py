from __future__ import annotations

import copy
from typing import Protocol

from .contracts import (
    MemoryApprovalProjection,
    MemoryCandidate,
    VersionMemoryInput,
    VersionMemoryProjection,
    _fingerprint_material,
)
from .projector import project_candidate


class MemoryAutomationPort(Protocol):
    def project(self, value: VersionMemoryInput) -> MemoryCandidate: ...

    def project_version(
        self, values: tuple[VersionMemoryInput, ...]
    ) -> VersionMemoryProjection: ...

    def approve(
        self, candidate: MemoryCandidate, approval: MemoryApprovalProjection
    ) -> MemoryCandidate: ...


class MemoryAutomationService:
    def project(self, value: VersionMemoryInput) -> MemoryCandidate:
        if type(value) is not VersionMemoryInput:
            raise TypeError("version memory input must be a typed projection")
        return project_candidate(value)

    def project_version(
        self, values: tuple[VersionMemoryInput, ...]
    ) -> VersionMemoryProjection:
        if not isinstance(values, tuple):
            raise ValueError("values must be a tuple")
        if any(type(item) is not VersionMemoryInput for item in values):
            raise TypeError("version memory input must be a typed projection")
        candidates = tuple(self.project(item) for item in copy.deepcopy(values))
        projection = VersionMemoryProjection.model_construct(
            candidates=candidates, fingerprint="sha256:" + "0" * 64
        )
        return VersionMemoryProjection.model_validate(
            {
                "candidates": candidates,
                "fingerprint": _fingerprint_material(projection),
            }
        )

    def approve(
        self, candidate: MemoryCandidate, approval: MemoryApprovalProjection
    ) -> MemoryCandidate:
        if type(candidate) is not MemoryCandidate or type(approval) is not MemoryApprovalProjection:
            raise TypeError("approval inputs must be typed projections")
        checked = MemoryCandidate.model_validate(copy.deepcopy(candidate))
        decision = MemoryApprovalProjection.model_validate(copy.deepcopy(approval))
        if (
            decision.memory_id != checked.memory_id
            or decision.candidate_fingerprint != checked.fingerprint
        ):
            raise ValueError("approval binding mismatch")
        from .contracts import MemoryReviewStatus

        status = (
            MemoryReviewStatus.APPROVED
            if decision.decision == "APPROVED"
            else MemoryReviewStatus.REJECTED
        )
        updated = checked.model_copy(
            update={"review_status": status, "fingerprint": "sha256:" + "0" * 64}
        )
        return MemoryCandidate.model_validate(
            {
                **updated.model_dump(mode="python"),
                "fingerprint": _fingerprint_material(updated),
            }
        )
