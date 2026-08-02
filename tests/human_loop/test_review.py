from __future__ import annotations

import pytest

from embedded_copilot.human_loop import (
    HumanLoopProgressUnavailable,
    HumanLoopRejected,
    HumanLoopState,
    HumanReviewDecision,
    create_human_loop_runtime,
)

from .conftest import (
    RecordingFeedbackPort,
    RecordingProgressSink,
    RecordingProposalPort,
    RecordingReviewPort,
    review_projection,
    review_request,
)


def _runtime(*, proposal=None, review=None, feedback=None, sink=None):
    proposal_port = proposal or RecordingProposalPort()
    review_port = review or RecordingReviewPort()
    feedback_port = feedback or RecordingFeedbackPort()
    progress_sink = sink or RecordingProgressSink()
    runtime = create_human_loop_runtime(
        proposal_port=proposal_port,
        review_port=review_port,
        feedback_port=feedback_port,
        progress_sink=progress_sink,
    )
    return runtime, proposal_port, review_port, feedback_port, progress_sink


@pytest.mark.parametrize(
    ("decision", "states", "final_state"),
    (
        (
            HumanReviewDecision.APPROVED,
            (
                HumanLoopState.GENERATED,
                HumanLoopState.WAITING_REVIEW,
                HumanLoopState.APPROVED,
                HumanLoopState.COMPLETED,
            ),
            HumanLoopState.COMPLETED,
        ),
        (
            HumanReviewDecision.CHANGES_REQUESTED,
            (
                HumanLoopState.GENERATED,
                HumanLoopState.WAITING_REVIEW,
                HumanLoopState.CHANGES_REQUESTED,
                HumanLoopState.REVISION_REQUIRED,
            ),
            HumanLoopState.REVISION_REQUIRED,
        ),
        (
            HumanReviewDecision.REJECTED,
            (
                HumanLoopState.GENERATED,
                HumanLoopState.WAITING_REVIEW,
                HumanLoopState.REJECTED,
            ),
            HumanLoopState.REJECTED,
        ),
    ),
)
def test_review_lifecycle_is_human_controlled(decision, states, final_state) -> None:
    request = review_request(decision)
    runtime, proposal_port, review_port, feedback_port, sink = _runtime()

    snapshot = runtime.human_loop_port().submit_review(request)

    assert snapshot.state is final_state
    assert tuple(event.state for event in sink.events) == states
    assert len(proposal_port.resolve_calls) == len(review_port.calls) == 1
    assert feedback_port.calls == []
    assert snapshot.review is not None
    assert snapshot.review is not review_port.calls[0].review


def test_review_output_binding_mismatch_fails_closed() -> None:
    request = review_request(HumanReviewDecision.APPROVED)
    invalid = review_projection(request).model_copy(
        update={"reviewer": "other-reviewer"}
    )
    runtime, *_ = _runtime(review=RecordingReviewPort(invalid))

    with pytest.raises(HumanLoopRejected):
        runtime.human_loop_port().submit_review(request)


def test_progress_failure_stops_before_review() -> None:
    review_port = RecordingReviewPort()
    runtime, proposal_port, _, _, _ = _runtime(
        review=review_port,
        sink=RecordingProgressSink(fail_at=1),
    )

    with pytest.raises(HumanLoopProgressUnavailable):
        runtime.human_loop_port().submit_review(
            review_request(HumanReviewDecision.APPROVED)
        )

    assert len(proposal_port.resolve_calls) == 1
    assert review_port.calls == []


def test_facade_does_not_expose_ports_or_state() -> None:
    runtime, *_ = _runtime()

    assert runtime.human_loop_port() is not None
    for attribute in (
        "proposal_port",
        "review_port",
        "feedback_port",
        "progress_sink",
        "state",
        "configuration",
    ):
        assert not hasattr(runtime, attribute)
