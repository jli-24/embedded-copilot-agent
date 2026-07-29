from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import (
    ApplyHumanApprovalRequest,
    ApplyVerificationRequest,
    CreateCandidateRequest,
    CreateReplacementCandidateRequest,
    EngineeringMemoryHistoryPage,
    EngineeringMemoryRequest,
    EngineeringMemoryResult,
    EngineeringMemorySnapshot,
    GetCandidateSnapshotRequest,
    GetHistoryRequest,
    GetVerifiedSnapshotRequest,
    MemoryAuditEvent,
    MemoryAuthorizationRequest,
    MemoryMutationResult,
    MemoryPermissionDecision,
    RevokeRecordRequest,
)


@runtime_checkable
class EngineeringMemoryPort(Protocol):
    def execute(self, request: EngineeringMemoryRequest) -> EngineeringMemoryResult: ...


@runtime_checkable
class EngineeringMemoryStorePort(Protocol):
    def create_candidate(
        self, request: CreateCandidateRequest, *, request_fingerprint: str
    ) -> MemoryMutationResult: ...

    def create_replacement_candidate(
        self,
        request: CreateReplacementCandidateRequest,
        *,
        request_fingerprint: str,
    ) -> MemoryMutationResult: ...

    def apply_verification(
        self, request: ApplyVerificationRequest, *, request_fingerprint: str
    ) -> MemoryMutationResult: ...

    def apply_human_approval(
        self, request: ApplyHumanApprovalRequest, *, request_fingerprint: str
    ) -> MemoryMutationResult: ...

    def revoke_record(
        self, request: RevokeRecordRequest, *, request_fingerprint: str
    ) -> MemoryMutationResult: ...

    def get_verified_snapshot(
        self, request: GetVerifiedSnapshotRequest
    ) -> EngineeringMemorySnapshot: ...

    def get_candidate_snapshot(
        self, request: GetCandidateSnapshotRequest
    ) -> EngineeringMemorySnapshot: ...

    def get_history(
        self, request: GetHistoryRequest
    ) -> EngineeringMemoryHistoryPage: ...


@runtime_checkable
class MemoryPermissionPort(Protocol):
    def authorize(
        self, request: MemoryAuthorizationRequest
    ) -> MemoryPermissionDecision: ...


@runtime_checkable
class MemoryAuditSink(Protocol):
    def record(self, event: MemoryAuditEvent) -> None: ...
