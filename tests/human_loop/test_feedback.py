from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.human_loop import (
    FeedbackProjection,
    FeedbackProjectionRequest,
    HumanLoopRejected,
    HumanReviewDecision,
    create_human_loop_runtime,
)

from .conftest import (
    NOW,
    RecordingFeedbackPort,
    RecordingProgressSink,
    RecordingProposalPort,
    RecordingReviewPort,
    feedback_projection,
    review_projection,
    review_request,
)


def _port(feedback_port):
    return create_human_loop_runtime(
        proposal_port=RecordingProposalPort(),
        review_port=RecordingReviewPort(),
        feedback_port=feedback_port,
        progress_sink=RecordingProgressSink(),
    ).human_loop_port()


def test_feedback_projection_is_deterministic_and_bound() -> None:
    review = review_projection(review_request())
    feedback_port = RecordingFeedbackPort()
    request = FeedbackProjectionRequest(review=review, timestamp=NOW)

    first = _port(feedback_port).project_feedback(request)
    second = _port(feedback_port).project_feedback(request)

    assert first == second
    assert first.review_fingerprint == review.fingerprint
    assert first.model_dump_json() == second.model_dump_json()
    assert len(feedback_port.calls) == 2
    assert feedback_port.calls[0] is not request


def test_non_change_review_cannot_project_feedback() -> None:
    review = review_projection(review_request(HumanReviewDecision.APPROVED))
    feedback_port = RecordingFeedbackPort()

    with pytest.raises(HumanLoopRejected):
        _port(feedback_port).project_feedback(
            FeedbackProjectionRequest(review=review, timestamp=NOW)
        )

    assert feedback_port.calls == []


def test_unsafe_or_unbound_feedback_is_rejected() -> None:
    review = review_projection(review_request())
    with pytest.raises(ValidationError):
        FeedbackProjection(
            proposal_id=review.proposal_id,
            review_fingerprint=review.fingerprint,
            change_type="RUN SHELL",
            target_reference="CAMERA_POWER",
            constraint="ADD_ESD_PROTECTION",
            priority="HIGH",
            safe_reference="datasheet-reference-1",
            fingerprint="sha256:" + "0" * 64,
        )

    invalid = feedback_projection(review).model_copy(
        update={"proposal_id": "other-proposal"}
    )
    feedback_port = RecordingFeedbackPort(invalid)
    with pytest.raises(HumanLoopRejected):
        _port(feedback_port).project_feedback(
            FeedbackProjectionRequest(review=review, timestamp=NOW)
        )
