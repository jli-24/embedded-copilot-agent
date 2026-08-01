from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.engineering_generation import ArtifactType
from embedded_copilot.human_loop import (
    FeedbackPriority,
    FeedbackProjection,
    HumanLoopProgressEvent,
    HumanReviewDecision,
    HumanReviewDecisionProjection,
    HumanReviewRequest,
    ProposalProjection,
    RevisionChange,
    RevisionContextReference,
    RevisionContextSource,
    RevisionProposal,
    feedback_projection_fingerprint,
    human_review_decision_fingerprint,
    proposal_projection_fingerprint,
    revision_proposal_fingerprint,
)

NOW = datetime(2026, 8, 6, 9, 0, tzinfo=UTC)


def proposal_projection() -> ProposalProjection:
    values = {
        "proposal_id": "proposal-1",
        "artifact_type": ArtifactType.HARDWARE_DESIGN,
        "artifact_version": 1,
        "summary": "Reviewable hardware design proposal.",
        "reference_ids": ("datasheet-reference-1",),
    }
    return ProposalProjection(
        **values,
        fingerprint=proposal_projection_fingerprint(**values),
    )


def review_request(
    decision: HumanReviewDecision = HumanReviewDecision.CHANGES_REQUESTED,
) -> HumanReviewRequest:
    return HumanReviewRequest(
        proposal_id="proposal-1",
        reviewer="engineer-1",
        decision=decision,
        review_comment=(
            "Add camera supply protection."
            if decision is HumanReviewDecision.CHANGES_REQUESTED
            else None
        ),
        timestamp=NOW,
    )


def review_projection(request: HumanReviewRequest) -> HumanReviewDecisionProjection:
    proposal = proposal_projection()
    values = {
        "proposal_id": request.proposal_id,
        "proposal_fingerprint": proposal.fingerprint,
        "reviewer": request.reviewer,
        "decision": request.decision,
        "review_comment": request.review_comment,
        "timestamp": request.timestamp,
    }
    return HumanReviewDecisionProjection(
        **values,
        fingerprint=human_review_decision_fingerprint(**values),
    )


def feedback_projection(
    review: HumanReviewDecisionProjection,
) -> FeedbackProjection:
    values = {
        "proposal_id": review.proposal_id,
        "review_fingerprint": review.fingerprint,
        "change_type": "POWER_PROTECTION_UPDATE",
        "target_reference": "CAMERA_POWER",
        "constraint": "ADD_ESD_PROTECTION",
        "priority": FeedbackPriority.HIGH,
        "safe_reference": "datasheet-reference-1",
    }
    return FeedbackProjection(
        **values,
        fingerprint=feedback_projection_fingerprint(**values),
    )


def context_references() -> tuple[RevisionContextReference, ...]:
    return (
        RevisionContextReference(
            source_type=RevisionContextSource.KNOWLEDGE_CONTEXT,
            reference_id="knowledge-reference-1",
            fingerprint="sha256:" + "1" * 64,
        ),
        RevisionContextReference(
            source_type=RevisionContextSource.MEMORY_CONTEXT,
            reference_id="memory-reference-1",
            fingerprint="sha256:" + "2" * 64,
        ),
    )


class RecordingProposalPort:
    def __init__(
        self,
        *,
        proposal: ProposalProjection | None = None,
        revision: RevisionProposal | None = None,
        resolve_error: Exception | None = None,
        revision_error: Exception | None = None,
    ) -> None:
        self.proposal = proposal or proposal_projection()
        self.revision = revision
        self.resolve_error = resolve_error
        self.revision_error = revision_error
        self.resolve_calls = []
        self.revision_calls = []

    def resolve(self, request):
        self.resolve_calls.append(request)
        if self.resolve_error is not None:
            raise self.resolve_error
        return self.proposal

    def prepare_revision(self, request):
        self.revision_calls.append(request)
        if self.revision_error is not None:
            raise self.revision_error
        if self.revision is not None:
            return self.revision
        values = {
            "revision_id": request.revision_id,
            "base_proposal_id": request.base_proposal_id,
            "changes": (
                RevisionChange(
                    target="power_module",
                    change="add_esd_protection",
                ),
            ),
            "rationale_summary": "Address the approved protection constraint.",
        }
        return RevisionProposal(
            **values,
            fingerprint=revision_proposal_fingerprint(**values),
        )


class RecordingReviewPort:
    def __init__(self, result=None, *, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls = []

    def review(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.result or review_projection(request.review)


class RecordingFeedbackPort:
    def __init__(self, result=None, *, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls = []

    def project(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.result or feedback_projection(request.review)


class RecordingProgressSink:
    def __init__(self, *, fail_at: int | None = None) -> None:
        self.events: list[HumanLoopProgressEvent] = []
        self.fail_at = fail_at

    def emit(self, event: HumanLoopProgressEvent) -> None:
        if event.sequence == self.fail_at:
            raise RuntimeError("database path C:/private and token=secret")
        self.events.append(event)


@pytest.fixture
def proposal_port() -> RecordingProposalPort:
    return RecordingProposalPort()


@pytest.fixture
def review_port() -> RecordingReviewPort:
    return RecordingReviewPort()


@pytest.fixture
def feedback_port() -> RecordingFeedbackPort:
    return RecordingFeedbackPort()


@pytest.fixture
def progress_sink() -> RecordingProgressSink:
    return RecordingProgressSink()
