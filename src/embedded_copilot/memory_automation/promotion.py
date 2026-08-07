from __future__ import annotations

import hashlib
from typing import Protocol

from embedded_copilot.engineering_memory import (
    ApplyHumanApprovalRequest,
    ApprovedEngineeringMemory,
    ApprovedEngineeringMemoryStorePort,
    ApprovalAudit,
    CreateCandidateRequest,
    EngineeringDecisionMemory,
    EngineeringMemoryPort,
    GetVerifiedSnapshotRequest,
    EngineeringMemoryType,
    HumanApprovalEvidence,
    MemoryProvenance,
    MemorySourceType,
    projection_from_snapshot,
)
from embedded_copilot.conversation_memory import ConversationMemoryCandidate

from .contracts import MemoryApprovalProjection, MemoryCandidate, MemoryReviewStatus, MemoryType
from .exceptions import MemoryApprovalRejected


class MemoryPromotionPort(Protocol):
    def promote(
        self,
        candidate: MemoryCandidate | ConversationMemoryCandidate,
        approval: MemoryApprovalProjection,
    ): ...


class MemoryPromotionService:
    def __init__(
        self,
        engineering_memory: EngineeringMemoryPort | None = None,
        *,
        approved_store: ApprovedEngineeringMemoryStorePort | None = None,
    ) -> None:
        if engineering_memory is None and approved_store is None:
            raise TypeError("promotion dependency is invalid")
        if engineering_memory is not None and not isinstance(
            engineering_memory, EngineeringMemoryPort
        ):
            raise TypeError("engineering memory port is invalid")
        if approved_store is not None and not isinstance(
            approved_store, ApprovedEngineeringMemoryStorePort
        ):
            raise TypeError("approved memory store is invalid")
        self._engineering_memory = engineering_memory
        self._approved_store = approved_store

    def promote(
        self,
        candidate: MemoryCandidate | ConversationMemoryCandidate,
        approval: MemoryApprovalProjection,
    ):
        if type(candidate) is ConversationMemoryCandidate:
            if (
                candidate.status.value != "PENDING_REVIEW"
                or approval.memory_id != candidate.candidate_id
                or approval.candidate_fingerprint != candidate.fingerprint
                or approval.decision != "APPROVED"
            ):
                raise MemoryApprovalRejected()
            from .projector import project_conversation_candidate

            projected = project_conversation_candidate(candidate)
            projected_approval = MemoryApprovalProjection(
                memory_id=projected.memory_id,
                candidate_fingerprint=projected.fingerprint,
                reviewer=approval.reviewer,
                decision=approval.decision,
                reviewed_at=approval.reviewed_at,
            )
            return self.promote(projected, projected_approval)
        if type(candidate) is not MemoryCandidate or type(approval) is not MemoryApprovalProjection:
            raise TypeError("promotion inputs must be typed projections")
        if (
            candidate.review_status is not MemoryReviewStatus.REVIEW_REQUIRED
            or approval.decision != "APPROVED"
            or approval.memory_id != candidate.memory_id
            or approval.candidate_fingerprint != candidate.fingerprint
        ):
            raise MemoryApprovalRejected()
        if self._approved_store is not None:
            return self._promote_approved_fact(candidate, approval)
        if candidate.memory_type not in (
            MemoryType.DECISION,
            MemoryType.ARCHITECTURE,
            MemoryType.REQUIREMENT,
        ):
            raise MemoryApprovalRejected()

        if self._engineering_memory is None:
            raise MemoryApprovalRejected()

        request_key = hashlib.sha256(candidate.fingerprint.encode()).hexdigest()[:20]
        request_id = f"promote-{request_key}"
        record_id = f"record-{request_key}"
        payload = EngineeringDecisionMemory(
            decision_topic=f"{candidate.memory_type.value.lower()}-{request_key[:8]}",
            decision=candidate.summary,
            rationale_summary=candidate.title,
        )
        provenance = MemoryProvenance(
            source_type=MemorySourceType.USER_INPUT,
            source_reference=candidate.source.source_reference,
            source_revision=candidate.fingerprint,
            created_by="memory-promotion",
            observed_at=candidate.source.observed_at,
        )
        created = self._engineering_memory.execute(
            CreateCandidateRequest(
                request_id=request_id,
                operation_id=f"create-{request_key}",
                project_id=candidate.source.source_id,
                memory_id=candidate.memory_id,
                caller="memory-promotion",
                requested_at=candidate.source.observed_at,
                expected_revision=0,
                record_id=record_id,
                payload=payload,
                provenance=provenance,
            )
        )
        self._engineering_memory.execute(
            ApplyHumanApprovalRequest(
                request_id=f"approve-{request_key}",
                operation_id=f"approval-{request_key}",
                project_id=candidate.source.source_id,
                memory_id=candidate.memory_id,
                caller="memory-promotion",
                requested_at=approval.reviewed_at,
                expected_revision=created.aggregate_revision,
                record_id=record_id,
                record_revision=0,
                approval=HumanApprovalEvidence(
                    approval_id=f"approval-{request_key}",
                    record_id=record_id,
                    record_revision=0,
                    approved_by=approval.reviewer,
                    reason_code="PROJECT_ACCEPTED",
                    approved_at=approval.reviewed_at,
                ),
            )
        )
        snapshot = self._engineering_memory.execute(
            GetVerifiedSnapshotRequest(
                request_id=f"snapshot-{request_key}",
                project_id=candidate.source.source_id,
                memory_id=candidate.memory_id,
                caller="memory-promotion",
                requested_at=approval.reviewed_at,
            )
        )
        return projection_from_snapshot(snapshot, record_id=record_id)

    def _promote_approved_fact(
        self,
        candidate: MemoryCandidate,
        approval: MemoryApprovalProjection,
    ) -> ApprovedEngineeringMemory:
        supported = {
            MemoryType.REQUIREMENT: EngineeringMemoryType.REQUIREMENT,
            MemoryType.ARCHITECTURE: EngineeringMemoryType.ARCHITECTURE,
            MemoryType.DECISION: EngineeringMemoryType.DECISION,
            MemoryType.INTERFACE: EngineeringMemoryType.INTERFACE,
        }
        memory_type = supported.get(candidate.memory_type)
        if memory_type is None:
            raise MemoryApprovalRejected()
        fact = ApprovedEngineeringMemory.create(
            memory_id=candidate.memory_id,
            project_id=candidate.source.source_id,
            source_reference=candidate.source.source_reference,
            memory_type=memory_type,
            summary=candidate.summary,
            decision=candidate.summary,
            reason=candidate.title,
            confidence=candidate.confidence,
            evidence=candidate.evidence_references,
            approval_audit=ApprovalAudit(
                approval_id=f"approval-{candidate.memory_id}",
                candidate_fingerprint=candidate.fingerprint,
                reviewer=approval.reviewer,
                decision="APPROVED",
                approved_at=approval.reviewed_at,
            ),
        )
        return self._approved_store.create_record(fact)


__all__ = ["MemoryPromotionPort", "MemoryPromotionService"]
