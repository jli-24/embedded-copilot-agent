"""Lifecycle, approval, replay, and failure tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from embedded_copilot.execution_runtime import (
    ExecutionApprovalContext,
    ExecutorType,
    ExecutionFailureCode,
    ExecutionProgressUnavailable,
    ExecutionRejected,
    ExecutionRuntime,
    ExecutionState,
    ExecutionVerificationStatus,
    create_execution_runtime,
    execution_approval_fingerprint,
)
from embedded_copilot.engineering_generation import ArtifactType
from embedded_copilot.human_loop import (
    HumanLoopState,
    HumanReviewDecision,
    HumanReviewDecisionProjection,
    HumanReviewSnapshot,
    ProposalProjection,
    human_review_decision_fingerprint,
    human_review_snapshot_fingerprint,
)

from .conftest import (
    FakeExecutor,
    FakeRegistry,
    FakeVerifier,
    NOW,
    RecordingProgressSink,
)


def _approval(snapshot, *, decision=HumanReviewDecision.APPROVED, state=None):
    if state is None:
        state = {
            HumanReviewDecision.APPROVED: HumanLoopState.COMPLETED,
            HumanReviewDecision.REJECTED: HumanLoopState.REJECTED,
            HumanReviewDecision.CHANGES_REQUESTED: HumanLoopState.REVISION_REQUIRED,
        }[decision]
    proposal = ProposalProjection(
        proposal_id=snapshot.plan.proposal.proposal_id,
        artifact_type=ArtifactType.FIRMWARE,
        artifact_version=1,
        summary="Reviewed execution proposal.",
        reference_ids=("artifact-input-1",),
        fingerprint=snapshot.plan.proposal.proposal_fingerprint,
    )
    review_fp = human_review_decision_fingerprint(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.fingerprint,
        reviewer="engineer-1",
        decision=decision,
        review_comment=(
            "Revision required."
            if decision is HumanReviewDecision.CHANGES_REQUESTED
            else None
        ),
        timestamp=NOW,
    )
    review = HumanReviewDecisionProjection(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.fingerprint,
        reviewer="engineer-1",
        decision=decision,
        review_comment=(
            "Revision required."
            if decision is HumanReviewDecision.CHANGES_REQUESTED
            else None
        ),
        timestamp=NOW,
        fingerprint=review_fp,
    )
    review_snapshot = HumanReviewSnapshot(
        proposal_id=proposal.proposal_id,
        proposal=proposal,
        state=state,
        review=review,
        progress_sequence=4,
        fingerprint=human_review_snapshot_fingerprint(
            proposal=proposal, state=state, review=review, progress_sequence=4
        ),
    )
    fp = execution_approval_fingerprint(
        execution_id=snapshot.plan.execution_id,
        ready_snapshot_fingerprint=snapshot.fingerprint,
        human_review=review_snapshot,
        reviewer="engineer-1",
        approval_timestamp=NOW,
    )
    return ExecutionApprovalContext(
        execution_id=snapshot.plan.execution_id,
        ready_snapshot_fingerprint=snapshot.fingerprint,
        human_review=review_snapshot,
        reviewer="engineer-1",
        approval_timestamp=NOW,
        fingerprint=fp,
    )


def _runtime(executor=None, verifier=None, sink=None):
    executor = executor or FakeExecutor()
    verifier = verifier or FakeVerifier()
    sink = sink or RecordingProgressSink()
    registry = FakeRegistry(executor)
    runtime = create_execution_runtime(
        executor_registry=registry,
        verification_port=verifier,
        progress_sink=sink,
    )
    return runtime, registry, executor, verifier, sink


def test_full_controlled_execution_lifecycle(preparation_request) -> None:
    before = preparation_request.model_dump_json()
    runtime, registry, executor, verifier, sink = _runtime()
    ready = runtime.execution_port().prepare_execution(preparation_request)
    assert ready.state is ExecutionState.READY
    terminal = runtime.execution_port().execute(ready, _approval(ready))
    assert terminal.state is ExecutionState.SUCCESS
    assert terminal.result is not None
    assert terminal.verification is not None
    assert len(registry.calls) == len(executor.calls) == len(verifier.calls) == 1
    assert [event.state for event in sink.events] == [
        ExecutionState.CREATED,
        ExecutionState.READY,
        ExecutionState.APPROVED,
        ExecutionState.RUNNING,
        ExecutionState.VERIFYING,
        ExecutionState.SUCCESS,
    ]
    assert preparation_request.model_dump_json() == before


def test_unknown_executor_returns_terminal_failure(preparation_request) -> None:
    sink = RecordingProgressSink()
    registry = FakeRegistry(None)
    runtime = create_execution_runtime(
        executor_registry=registry,
        verification_port=FakeVerifier(),
        progress_sink=sink,
    )
    snapshot = runtime.execution_port().prepare_execution(preparation_request)
    assert snapshot.state is ExecutionState.FAILED
    assert snapshot.failure_code is ExecutionFailureCode.EXECUTOR_UNAVAILABLE
    assert [event.state for event in sink.events] == [
        ExecutionState.CREATED,
        ExecutionState.FAILED,
    ]


def test_wrong_executor_binding_has_no_fallback(preparation_request) -> None:
    wrong = FakeExecutor(ExecutorType.DEBUG)
    runtime, registry, _, _, _ = _runtime(wrong)
    snapshot = runtime.execution_port().prepare_execution(preparation_request)
    assert snapshot.state is ExecutionState.FAILED
    assert snapshot.failure_code is ExecutionFailureCode.EXECUTOR_REJECTED
    assert len(registry.calls) == 1
    assert not wrong.calls


@pytest.mark.parametrize(
    ("decision", "state", "failure"),
    [
        (
            HumanReviewDecision.REJECTED,
            ExecutionState.CANCELLED,
            ExecutionFailureCode.APPROVAL_DENIED,
        ),
        (
            HumanReviewDecision.CHANGES_REQUESTED,
            ExecutionState.CANCELLED,
            ExecutionFailureCode.REVISION_REQUIRED,
        ),
    ],
)
def test_human_decision_cancels_without_executor(
    preparation_request, decision, state, failure
) -> None:
    runtime, _, executor, verifier, _ = _runtime()
    ready = runtime.execution_port().prepare_execution(preparation_request)
    result = runtime.execution_port().execute(
        ready, _approval(ready, decision=decision)
    )
    assert result.state is state
    assert result.failure_code is failure
    assert not executor.calls
    assert not verifier.calls


def test_approval_binding_mismatch_is_rejected(preparation_request) -> None:
    runtime, _, executor, _, _ = _runtime()
    ready = runtime.execution_port().prepare_execution(preparation_request)
    approval = _approval(ready).model_copy(
        update={"ready_snapshot_fingerprint": "sha256:" + "f" * 64}
    )
    with pytest.raises(ExecutionRejected, match="execution request was rejected"):
        runtime.execution_port().execute(ready, approval)
    assert not executor.calls


def test_sequential_and_cross_runtime_replay_are_rejected(preparation_request) -> None:
    runtime, _, executor, _, _ = _runtime()
    ready = runtime.execution_port().prepare_execution(preparation_request)
    approval = _approval(ready)
    runtime.execution_port().execute(ready, approval)
    with pytest.raises(ExecutionRejected):
        runtime.execution_port().execute(ready, approval)
    other, *_ = _runtime()
    with pytest.raises(ExecutionRejected):
        other.execution_port().execute(ready, approval)
    assert len(executor.calls) == 1


def test_concurrent_replay_invokes_executor_once(preparation_request) -> None:
    runtime, _, executor, _, _ = _runtime()
    ready = runtime.execution_port().prepare_execution(preparation_request)
    approval = _approval(ready)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(runtime.execution_port().execute, ready, approval)
            for _ in range(2)
        ]
    successes = [future.result() for future in futures if future.exception() is None]
    failures = [
        future.exception() for future in futures if future.exception() is not None
    ]
    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], ExecutionRejected)
    assert len(executor.calls) == 1


@pytest.mark.parametrize(
    ("behavior", "expected_state", "failure"),
    [
        (
            lambda _request: (_ for _ in ()).throw(TimeoutError("secret")),
            ExecutionState.TIMEOUT,
            ExecutionFailureCode.EXECUTOR_TIMEOUT,
        ),
        (
            lambda _request: (_ for _ in ()).throw(RuntimeError("secret")),
            ExecutionState.FAILED,
            ExecutionFailureCode.EXECUTOR_FAILED,
        ),
        (
            lambda _request: {"stdout": "secret"},
            ExecutionState.FAILED,
            ExecutionFailureCode.EXECUTOR_REJECTED,
        ),
    ],
)
def test_executor_failures_are_terminal_and_sanitized(
    preparation_request, behavior, expected_state, failure
) -> None:
    runtime, _, _, verifier, _ = _runtime(FakeExecutor(behavior=behavior))
    ready = runtime.execution_port().prepare_execution(preparation_request)
    result = runtime.execution_port().execute(ready, _approval(ready))
    assert result.state is expected_state
    assert result.failure_code is failure
    assert result.result is None
    assert not verifier.calls
    assert "secret" not in result.model_dump_json()


def test_verification_invalid_returns_failed_snapshot(preparation_request) -> None:
    verifier = FakeVerifier(ExecutionVerificationStatus.INVALID)
    runtime, _, executor, _, _ = _runtime(verifier=verifier)
    ready = runtime.execution_port().prepare_execution(preparation_request)
    result = runtime.execution_port().execute(ready, _approval(ready))
    assert result.state is ExecutionState.FAILED
    assert result.failure_code is ExecutionFailureCode.VERIFICATION_INVALID
    assert len(executor.calls) == len(verifier.calls) == 1


def test_progress_failure_is_fail_closed_and_not_replayable(
    preparation_request,
) -> None:
    sink = RecordingProgressSink(fail_on_sequence=3)
    runtime, _, executor, _, _ = _runtime(sink=sink)
    ready = runtime.execution_port().prepare_execution(preparation_request)
    approval = _approval(ready)
    with pytest.raises(
        ExecutionProgressUnavailable, match="execution progress unavailable"
    ):
        runtime.execution_port().execute(ready, approval)
    with pytest.raises(ExecutionRejected):
        runtime.execution_port().execute(ready, approval)
    assert not executor.calls


def test_facade_does_not_expose_internal_state() -> None:
    runtime, *_ = _runtime()
    assert runtime.execution_port() is runtime.execution_port()
    for name in (
        "registry",
        "executor",
        "bindings",
        "ledger",
        "verification_port",
        "progress_sink",
    ):
        assert not hasattr(runtime, name)
    with pytest.raises(TypeError, match="composition factory"):
        ExecutionRuntime(runtime.execution_port())


def test_factory_rejects_invalid_dependencies() -> None:
    with pytest.raises(ExecutionRejected, match="configuration was rejected"):
        create_execution_runtime(
            executor_registry=object(),
            verification_port=FakeVerifier(),
            progress_sink=RecordingProgressSink(),
        )


def test_execution_id_is_reserved_for_runtime_lifetime(preparation_request) -> None:
    runtime, registry, *_ = _runtime()
    runtime.execution_port().prepare_execution(preparation_request)
    with pytest.raises(ExecutionRejected):
        runtime.execution_port().prepare_execution(preparation_request)
    assert len(registry.calls) == 1
