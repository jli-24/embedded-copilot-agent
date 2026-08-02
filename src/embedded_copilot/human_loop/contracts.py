"""Protocol boundaries for the Human Loop Runtime."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.human_loop.models import (
    FeedbackProjection,
    FeedbackProjectionRequest,
    HumanLoopProgressEvent,
    HumanReviewRequest,
    HumanReviewDecisionProjection,
    HumanReviewSnapshot,
    HumanReviewSubmissionRequest,
    ProposalProjection,
    ProposalResolutionRequest,
    RevisionGenerationRequest,
    RevisionPreparationRequest,
    RevisionProposal,
)


@runtime_checkable
class HumanLoopPort(Protocol):
    def submit_review(self, request: HumanReviewRequest) -> HumanReviewSnapshot: ...

    def project_feedback(
        self, request: FeedbackProjectionRequest
    ) -> FeedbackProjection: ...

    def prepare_revision(
        self, request: RevisionPreparationRequest
    ) -> RevisionProposal: ...


@runtime_checkable
class DesignProposalPort(Protocol):
    def resolve(self, request: ProposalResolutionRequest) -> ProposalProjection: ...

    def prepare_revision(
        self, request: RevisionGenerationRequest
    ) -> RevisionProposal: ...


@runtime_checkable
class HumanReviewPort(Protocol):
    def review(
        self, request: HumanReviewSubmissionRequest
    ) -> HumanReviewDecisionProjection: ...


@runtime_checkable
class FeedbackProjectionPort(Protocol):
    def project(self, request: FeedbackProjectionRequest) -> FeedbackProjection: ...


@runtime_checkable
class HumanLoopProgressSink(Protocol):
    def emit(self, event: HumanLoopProgressEvent) -> None: ...
