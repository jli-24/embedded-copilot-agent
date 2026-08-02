from __future__ import annotations

import pytest

from embedded_copilot.human_loop import (
    FeedbackProjectionRequest,
    HumanLoopRejected,
    HumanReviewDecision,
    RevisionPreparationRequest,
    create_human_loop_runtime,
)

from .conftest import (
    NOW,
    RecordingFeedbackPort,
    RecordingProgressSink,
    RecordingProposalPort,
    RecordingReviewPort,
    context_references,
    feedback_projection,
    proposal_projection,
    review_projection,
    review_request,
)


def _runtime(proposal_port=None):
    selected = proposal_port or RecordingProposalPort()
    return (
        create_human_loop_runtime(
            proposal_port=selected,
            review_port=RecordingReviewPort(),
            feedback_port=RecordingFeedbackPort(),
            progress_sink=RecordingProgressSink(),
        ).human_loop_port(),
        selected,
    )


def _request(decision=HumanReviewDecision.CHANGES_REQUESTED):
    proposal = proposal_projection()
    review = review_projection(review_request(decision))
    feedback = (
        feedback_projection(review)
        if decision is HumanReviewDecision.CHANGES_REQUESTED
        else feedback_projection(review_projection(review_request()))
    )
    return RevisionPreparationRequest(
        revision_id="revision-2",
        proposal=proposal,
        review=review,
        feedback=feedback,
        context_references=context_references(),
        timestamp=NOW,
    )


def test_valid_revision_context_produces_reviewable_proposal() -> None:
    request = _request()
    port, proposal_port = _runtime()
    before = request.model_dump(mode="python")

    revision = port.prepare_revision(request)

    assert revision.revision_id == request.revision_id
    assert revision.base_proposal_id == request.proposal.proposal_id
    assert len(proposal_port.revision_calls) == 1
    context = proposal_port.revision_calls[0].context
    assert context.proposal_fingerprint == request.proposal.fingerprint
    assert context.feedback_fingerprint == request.feedback.fingerprint
    assert request.model_dump(mode="python") == before
    assert revision is not proposal_port.revision


def test_unauthorized_revision_never_calls_proposal_port() -> None:
    proposal_port = RecordingProposalPort()
    port, _ = _runtime(proposal_port)

    with pytest.raises(HumanLoopRejected):
        port.prepare_revision(_request(HumanReviewDecision.APPROVED))

    assert proposal_port.revision_calls == []


def test_revision_rejects_fingerprint_mismatch() -> None:
    request = _request()
    tampered_feedback = request.feedback.model_copy(
        update={"fingerprint": "sha256:" + "0" * 64}
    )
    tampered = request.model_copy(update={"feedback": tampered_feedback})
    port, proposal_port = _runtime()

    with pytest.raises(HumanLoopRejected):
        port.prepare_revision(tampered)

    assert proposal_port.revision_calls == []


def test_revision_requires_verified_knowledge_and_memory_references() -> None:
    request = _request()
    missing_memory = request.model_copy(
        update={"context_references": request.context_references[:1]}
    )
    port, proposal_port = _runtime()

    with pytest.raises(HumanLoopRejected):
        port.prepare_revision(missing_memory)

    assert proposal_port.revision_calls == []


def test_feedback_operation_does_not_prepare_revision() -> None:
    review = review_projection(review_request())
    proposal_port = RecordingProposalPort()
    runtime = create_human_loop_runtime(
        proposal_port=proposal_port,
        review_port=RecordingReviewPort(),
        feedback_port=RecordingFeedbackPort(),
        progress_sink=RecordingProgressSink(),
    )

    runtime.human_loop_port().project_feedback(
        FeedbackProjectionRequest(review=review, timestamp=NOW)
    )

    assert proposal_port.resolve_calls == []
    assert proposal_port.revision_calls == []
