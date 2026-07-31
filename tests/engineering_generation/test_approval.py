from __future__ import annotations

import pytest

from embedded_copilot.engineering_generation import (
    ArtifactApprovalDecision,
    ArtifactApprovalRejected,
    ArtifactLifecycleState,
    GenerationApprovalStatus,
    GenerationFailureCode,
)

from .conftest import RecordingApprovalPolicy, approval_for
from .test_runtime import _runtime


def test_human_approved_proposal_completes_with_reference(generation_request) -> None:
    runtime, _, _, _, policy, sink = _runtime(generation_request)
    port = runtime.generation_port()
    waiting = port.generate_artifact(generation_request)

    completed = port.approve_artifact(
        waiting,
        approval_for(waiting, ArtifactApprovalDecision.APPROVED),
    )

    assert completed.state is ArtifactLifecycleState.COMPLETED
    assert completed.approved_artifact is not None
    assert (
        completed.approved_artifact.proposal_fingerprint == waiting.proposal.fingerprint
    )
    assert [event.state for event in sink.events[-2:]] == [
        ArtifactLifecycleState.APPROVED,
        ArtifactLifecycleState.COMPLETED,
    ]
    assert len(policy.calls) == 1


def test_human_rejection_does_not_call_approval_policy(generation_request) -> None:
    runtime, _, _, _, policy, _ = _runtime(generation_request)
    port = runtime.generation_port()
    waiting = port.generate_artifact(generation_request)

    rejected = port.approve_artifact(
        waiting,
        approval_for(waiting, ArtifactApprovalDecision.REJECTED),
    )

    assert rejected.state is ArtifactLifecycleState.REJECTED
    assert rejected.failure_code is GenerationFailureCode.APPROVAL_REJECTED
    assert policy.calls == []


def test_policy_denial_rejects_approved_human_decision(generation_request) -> None:
    policy = RecordingApprovalPolicy(status=GenerationApprovalStatus.DENIED)
    runtime, *_ = _runtime(generation_request, policy=policy)
    port = runtime.generation_port()
    waiting = port.generate_artifact(generation_request)

    rejected = port.approve_artifact(
        waiting,
        approval_for(waiting, ArtifactApprovalDecision.APPROVED),
    )

    assert rejected.state is ArtifactLifecycleState.REJECTED
    assert rejected.failure_code is GenerationFailureCode.APPROVAL_REJECTED


def test_approval_fingerprint_mismatch_is_rejected(generation_request) -> None:
    runtime, *_ = _runtime(generation_request)
    port = runtime.generation_port()
    waiting = port.generate_artifact(generation_request)
    approval = approval_for(waiting, ArtifactApprovalDecision.APPROVED)

    with pytest.raises(ArtifactApprovalRejected):
        port.approve_artifact(
            waiting,
            approval.model_copy(update={"artifact_fingerprint": "sha256:" + "0" * 64}),
        )
