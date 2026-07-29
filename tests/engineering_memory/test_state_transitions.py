from datetime import UTC, datetime

import pytest

from embedded_copilot.engineering_memory import (
    ApplyHumanApprovalRequest,
    ApplyVerificationRequest,
    CreateCandidateRequest,
    CreateReplacementCandidateRequest,
    EngineeringDecisionMemory,
    GetHistoryRequest,
    HumanApprovalEvidence,
    MemoryProvenance,
    MemorySourceType,
    MemoryStateTransitionRejected,
    MemoryStatus,
    RevokeRecordRequest,
    VerificationHistoryMemory,
)
from embedded_copilot.engineering_memory.stores.in_memory import (
    InMemoryEngineeringMemoryStore,
)
from embedded_copilot.tool_runtime import (
    BuildStatus,
    FirmwareBuildOutput,
    ToolCompiler,
)
from embedded_copilot.verification_agent import (
    FirmwareVerificationSubject,
    VerificationFinding,
    VerificationFindingCategory,
    VerificationRequest,
    VerificationResult,
    VerificationSeverity,
    VerificationStatus,
    VerificationSubjectType,
)

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)


def _provenance() -> MemoryProvenance:
    return MemoryProvenance(
        source_type=MemorySourceType.USER_INPUT,
        source_reference="source-1",
        source_revision="revision-1",
        created_by="caller-1",
        observed_at=NOW,
    )


def _decision(topic: str = "rtos-choice") -> EngineeringDecisionMemory:
    return EngineeringDecisionMemory(
        decision_topic=topic,
        decision="Use FreeRTOS",
        rationale_summary="Platform support and deterministic scheduling",
    )


def _create(payload=None, **changes) -> CreateCandidateRequest:
    values = {
        "request_id": "create-1",
        "operation_id": "create-op-1",
        "project_id": "project-1",
        "memory_id": "memory-1",
        "caller": "caller-1",
        "requested_at": NOW,
        "expected_revision": 0,
        "record_id": "record-1",
        "payload": payload or _decision(),
        "provenance": _provenance(),
    }
    values.update(changes)
    return CreateCandidateRequest(**values)


def _verification(
    status: VerificationStatus,
    *,
    record_id: str = "record-1",
    record_revision: int = 0,
    expected_revision: int = 1,
    operation_id: str = "verify-op-1",
) -> ApplyVerificationRequest:
    verification_id = f"verify-{operation_id}"
    subject = FirmwareVerificationSubject(
        build_output=FirmwareBuildOutput(
            build_status=BuildStatus.SUCCESS,
            compiler=ToolCompiler.GCC,
            warnings_count=0,
            error_count=0,
            summary="Caller supplied deterministic build evidence.",
        )
    )
    verification_request = VerificationRequest(
        request_id=verification_id,
        subject_type=VerificationSubjectType.FIRMWARE,
        subject=subject,
        context_id=f"memory:project-1:memory-1:{record_id}:{record_revision}",
        requested_at=NOW,
    )
    findings = ()
    if status is not VerificationStatus.PASS:
        findings = (
            VerificationFinding(
                severity=VerificationSeverity.HIGH,
                category=VerificationFindingCategory.BUILD_STATUS,
                message="Current proposal requires further review.",
                evidence=("Caller supplied deterministic rule evidence.",),
                recommendation="Review the proposal before accepting it.",
            ),
        )
    verification_result = VerificationResult(
        request_id=verification_id,
        status=status,
        findings=findings,
        confidence=1.0 if status is not VerificationStatus.REVIEW_REQUIRED else 0.5,
        summary="Deterministic verification result supplied by the caller.",
    )
    return ApplyVerificationRequest(
        request_id=f"apply-{operation_id}",
        operation_id=operation_id,
        project_id="project-1",
        memory_id="memory-1",
        caller="caller-1",
        requested_at=NOW,
        expected_revision=expected_revision,
        record_id=record_id,
        record_revision=record_revision,
        verification_request=verification_request,
        verification_result=verification_result,
    )


def _history(store):
    return store.get_history(
        GetHistoryRequest(
            request_id="history-1",
            project_id="project-1",
            memory_id="memory-1",
            caller="caller-1",
            requested_at=NOW,
        )
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        (VerificationStatus.PASS, MemoryStatus.VERIFIED),
        (VerificationStatus.FAIL, MemoryStatus.REJECTED),
        (VerificationStatus.REVIEW_REQUIRED, MemoryStatus.CANDIDATE),
    ),
)
def test_verification_status_maps_deterministically(status, expected) -> None:
    store = InMemoryEngineeringMemoryStore()
    store.create_candidate(_create(), request_fingerprint="sha256:" + "a" * 64)
    result = store.apply_verification(
        _verification(status), request_fingerprint="sha256:" + "b" * 64
    )
    assert result.affected_records[0].status is expected
    assert result.affected_records[0].record_revision == 1
    assert result.aggregate_revision == 2
    record = _history(store).records[0]
    assert record.verification_bindings[-1].result_status is status
    if status is VerificationStatus.REVIEW_REQUIRED:
        assert (
            record.state_history[-1].from_status,
            record.state_history[-1].to_status,
        ) == (MemoryStatus.CANDIDATE, MemoryStatus.CANDIDATE)


def test_human_approval_is_restricted_and_revoke_preserves_history() -> None:
    store = InMemoryEngineeringMemoryStore()
    store.create_candidate(_create(), request_fingerprint="sha256:" + "a" * 64)
    approval = HumanApprovalEvidence(
        approval_id="approval-1",
        record_id="record-1",
        record_revision=0,
        approved_by="reviewer-1",
        reason_code="PROJECT_ACCEPTED",
        approved_at=NOW,
    )
    approved = store.apply_human_approval(
        ApplyHumanApprovalRequest(
            request_id="approve-1",
            operation_id="approve-op-1",
            project_id="project-1",
            memory_id="memory-1",
            caller="caller-1",
            requested_at=NOW,
            expected_revision=1,
            record_id="record-1",
            record_revision=0,
            approval=approval,
        ),
        request_fingerprint="sha256:" + "b" * 64,
    )
    assert approved.affected_records[0].status is MemoryStatus.VERIFIED
    revoked = store.revoke_record(
        RevokeRecordRequest(
            request_id="revoke-1",
            operation_id="revoke-op-1",
            project_id="project-1",
            memory_id="memory-1",
            caller="caller-1",
            requested_at=NOW,
            expected_revision=2,
            record_id="record-1",
            record_revision=1,
            reason_code="NO_LONGER_VALID",
        ),
        request_fingerprint="sha256:" + "c" * 64,
    )
    assert revoked.affected_records[0].status is MemoryStatus.REVOKED
    assert len(_history(store).records[0].state_history) == 3


def test_verification_history_is_append_only_and_not_replaceable_or_approvable() -> (
    None
):
    store = InMemoryEngineeringMemoryStore()
    payload = VerificationHistoryMemory(
        verification_request_id="verification-1",
        subject_type=VerificationSubjectType.FIRMWARE,
        verification_status=VerificationStatus.PASS,
        confidence_basis="Complete deterministic rule evidence.",
    )
    store.create_candidate(_create(payload), request_fingerprint="sha256:" + "a" * 64)
    with pytest.raises(MemoryStateTransitionRejected):
        store.create_candidate(
            _create(
                payload,
                request_id="create-2",
                operation_id="create-op-2",
                expected_revision=1,
                record_id="record-2",
            ),
            request_fingerprint="sha256:" + "b" * 64,
        )
    with pytest.raises(MemoryStateTransitionRejected):
        store.create_replacement_candidate(
            CreateReplacementCandidateRequest(
                request_id="replace-1",
                operation_id="replace-op-1",
                project_id="project-1",
                memory_id="memory-1",
                caller="caller-1",
                requested_at=NOW,
                expected_revision=1,
                record_id="record-2",
                payload=payload,
                provenance=_provenance(),
                supersedes_record_id="record-1",
            ),
            request_fingerprint="sha256:" + "c" * 64,
        )


def test_replacement_activation_changes_both_records_atomically() -> None:
    store = InMemoryEngineeringMemoryStore()
    store.create_candidate(_create(), request_fingerprint="sha256:" + "a" * 64)
    store.apply_verification(
        _verification(VerificationStatus.PASS),
        request_fingerprint="sha256:" + "b" * 64,
    )
    replacement = CreateReplacementCandidateRequest(
        request_id="replace-1",
        operation_id="replace-op-1",
        project_id="project-1",
        memory_id="memory-1",
        caller="caller-1",
        requested_at=NOW,
        expected_revision=2,
        record_id="record-2",
        payload=EngineeringDecisionMemory(
            decision_topic="rtos-choice",
            decision="Use Zephyr",
            rationale_summary="Updated project portability requirement",
        ),
        provenance=_provenance(),
        supersedes_record_id="record-1",
    )
    store.create_replacement_candidate(
        replacement, request_fingerprint="sha256:" + "c" * 64
    )
    activated = store.apply_verification(
        _verification(
            VerificationStatus.PASS,
            record_id="record-2",
            expected_revision=3,
            operation_id="verify-op-2",
        ),
        request_fingerprint="sha256:" + "d" * 64,
    )
    records = {record.record_id: record for record in _history(store).records}
    assert activated.aggregate_revision == 4
    assert records["record-1"].status is MemoryStatus.SUPERSEDED
    assert records["record-1"].record_revision == 2
    assert records["record-2"].status is MemoryStatus.VERIFIED
    assert records["record-2"].record_revision == 1
    assert records["record-1"].superseded_by_record_id == "record-2"


def _store_with_replacement() -> InMemoryEngineeringMemoryStore:
    store = InMemoryEngineeringMemoryStore()
    store.create_candidate(_create(), request_fingerprint="sha256:" + "a" * 64)
    store.apply_verification(
        _verification(VerificationStatus.PASS),
        request_fingerprint="sha256:" + "b" * 64,
    )
    store.create_replacement_candidate(
        CreateReplacementCandidateRequest(
            request_id="replace-1",
            operation_id="replace-op-1",
            project_id="project-1",
            memory_id="memory-1",
            caller="caller-1",
            requested_at=NOW,
            expected_revision=2,
            record_id="record-2",
            payload=EngineeringDecisionMemory(
                decision_topic="rtos-choice",
                decision="Use Zephyr",
                rationale_summary="Updated project portability requirement",
            ),
            provenance=_provenance(),
            supersedes_record_id="record-1",
        ),
        request_fingerprint="sha256:" + "c" * 64,
    )
    return store


def test_human_approval_activates_replacement_atomically() -> None:
    store = _store_with_replacement()
    approval = HumanApprovalEvidence(
        approval_id="approval-replacement",
        record_id="record-2",
        record_revision=0,
        approved_by="reviewer-1",
        reason_code="PROJECT_ACCEPTED",
        approved_at=NOW,
    )
    result = store.apply_human_approval(
        ApplyHumanApprovalRequest(
            request_id="approve-replacement",
            operation_id="approve-replacement-op",
            project_id="project-1",
            memory_id="memory-1",
            caller="caller-1",
            requested_at=NOW,
            expected_revision=3,
            record_id="record-2",
            record_revision=0,
            approval=approval,
        ),
        request_fingerprint="sha256:" + "d" * 64,
    )
    records = {record.record_id: record for record in _history(store).records}
    assert result.aggregate_revision == 4
    assert records["record-1"].status is MemoryStatus.SUPERSEDED
    assert records["record-2"].status is MemoryStatus.VERIFIED


@pytest.mark.parametrize(
    "status", (VerificationStatus.FAIL, VerificationStatus.REVIEW_REQUIRED)
)
def test_nonpassing_replacement_leaves_old_verified_active(status) -> None:
    store = _store_with_replacement()
    store.apply_verification(
        _verification(
            status,
            record_id="record-2",
            expected_revision=3,
            operation_id=f"replacement-{status.value.lower()}",
        ),
        request_fingerprint="sha256:" + "d" * 64,
    )
    records = {record.record_id: record for record in _history(store).records}
    assert records["record-1"].status is MemoryStatus.VERIFIED
    assert records["record-2"].status is (
        MemoryStatus.REJECTED
        if status is VerificationStatus.FAIL
        else MemoryStatus.CANDIDATE
    )


def test_revoked_replacement_leaves_old_verified_active() -> None:
    store = _store_with_replacement()
    store.revoke_record(
        RevokeRecordRequest(
            request_id="revoke-replacement",
            operation_id="revoke-replacement-op",
            project_id="project-1",
            memory_id="memory-1",
            caller="caller-1",
            requested_at=NOW,
            expected_revision=3,
            record_id="record-2",
            record_revision=0,
            reason_code="NO_LONGER_VALID",
        ),
        request_fingerprint="sha256:" + "d" * 64,
    )
    records = {record.record_id: record for record in _history(store).records}
    assert records["record-1"].status is MemoryStatus.VERIFIED
    assert records["record-2"].status is MemoryStatus.REVOKED
