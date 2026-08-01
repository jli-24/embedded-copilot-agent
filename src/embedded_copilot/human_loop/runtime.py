"""Deterministic orchestration for human review and revision proposals."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from embedded_copilot.human_loop.contracts import (
    DesignProposalPort,
    FeedbackProjectionPort,
    HumanLoopPort,
    HumanLoopProgressSink,
    HumanReviewPort,
)
from embedded_copilot.human_loop.exceptions import (
    FeedbackProjectionUnavailable,
    HumanLoopProgressUnavailable,
    HumanLoopRejected,
    HumanReviewUnavailable,
    RevisionProposalUnavailable,
)
from embedded_copilot.human_loop.models import (
    FeedbackProjection,
    FeedbackProjectionRequest,
    HumanLoopProgressEvent,
    HumanLoopProgressEventType,
    HumanLoopState,
    HumanReviewDecision,
    HumanReviewDecisionProjection,
    HumanReviewRequest,
    HumanReviewSnapshot,
    HumanReviewSubmissionRequest,
    ProposalProjection,
    ProposalResolutionRequest,
    RevisionContext,
    RevisionContextSource,
    RevisionGenerationRequest,
    RevisionPreparationRequest,
    RevisionProposal,
    human_review_snapshot_fingerprint,
    revision_context_fingerprint,
)

_ContractT = TypeVar("_ContractT", bound=BaseModel)


def _typed_copy(value: object, expected_type: type[_ContractT]) -> _ContractT:
    """Deep-copy a typed contract without a serialization round-trip."""
    if type(value) is not expected_type:
        raise HumanLoopRejected("human loop contract is invalid")
    try:
        copied = value.model_copy(deep=True)
        return expected_type.model_validate(copied)
    except (TypeError, ValueError, ValidationError):
        raise HumanLoopRejected("human loop contract is invalid") from None


class _HumanLoopService(HumanLoopPort):
    __slots__ = (
        "__feedback_port",
        "__progress_sink",
        "__proposal_port",
        "__review_port",
    )

    def __init__(
        self,
        *,
        proposal_port: DesignProposalPort,
        review_port: HumanReviewPort,
        feedback_port: FeedbackProjectionPort,
        progress_sink: HumanLoopProgressSink,
    ) -> None:
        self.__proposal_port = proposal_port
        self.__review_port = review_port
        self.__feedback_port = feedback_port
        self.__progress_sink = progress_sink

    def submit_review(self, request: HumanReviewRequest) -> HumanReviewSnapshot:
        safe_request = _typed_copy(request, HumanReviewRequest)
        try:
            raw_proposal = self.__proposal_port.resolve(
                ProposalResolutionRequest(proposal_id=safe_request.proposal_id)
            )
        except Exception:
            raise HumanReviewUnavailable("human review is unavailable") from None
        proposal = _typed_copy(raw_proposal, ProposalProjection)
        if proposal.proposal_id != safe_request.proposal_id:
            raise HumanLoopRejected("proposal binding is invalid")

        sequence = self._emit(
            proposal_id=proposal.proposal_id,
            state=HumanLoopState.GENERATED,
            event=HumanLoopProgressEventType.PROPOSAL_GENERATED,
            sequence=1,
            timestamp=safe_request.timestamp,
        )
        sequence = self._emit(
            proposal_id=proposal.proposal_id,
            state=HumanLoopState.WAITING_REVIEW,
            event=HumanLoopProgressEventType.REVIEW_WAITING,
            sequence=sequence + 1,
            timestamp=safe_request.timestamp,
        )
        submission = HumanReviewSubmissionRequest(
            proposal=proposal,
            review=safe_request,
        )
        try:
            raw_review = self.__review_port.review(submission)
        except Exception:
            raise HumanReviewUnavailable("human review is unavailable") from None
        review = _typed_copy(raw_review, HumanReviewDecisionProjection)
        self._validate_review(review, proposal, safe_request)

        if review.decision is HumanReviewDecision.APPROVED:
            sequence = self._emit(
                proposal_id=proposal.proposal_id,
                state=HumanLoopState.APPROVED,
                event=HumanLoopProgressEventType.REVIEW_APPROVED,
                sequence=sequence + 1,
                timestamp=review.timestamp,
            )
            sequence = self._emit(
                proposal_id=proposal.proposal_id,
                state=HumanLoopState.COMPLETED,
                event=HumanLoopProgressEventType.REVIEW_COMPLETED,
                sequence=sequence + 1,
                timestamp=review.timestamp,
            )
            return self._snapshot(
                proposal=proposal,
                review=review,
                state=HumanLoopState.COMPLETED,
                progress_sequence=sequence,
            )
        if review.decision is HumanReviewDecision.CHANGES_REQUESTED:
            sequence = self._emit(
                proposal_id=proposal.proposal_id,
                state=HumanLoopState.CHANGES_REQUESTED,
                event=HumanLoopProgressEventType.CHANGES_REQUESTED,
                sequence=sequence + 1,
                timestamp=review.timestamp,
            )
            sequence = self._emit(
                proposal_id=proposal.proposal_id,
                state=HumanLoopState.REVISION_REQUIRED,
                event=HumanLoopProgressEventType.REVISION_REQUIRED,
                sequence=sequence + 1,
                timestamp=review.timestamp,
            )
            return self._snapshot(
                proposal=proposal,
                review=review,
                state=HumanLoopState.REVISION_REQUIRED,
                progress_sequence=sequence,
            )
        sequence = self._emit(
            proposal_id=proposal.proposal_id,
            state=HumanLoopState.REJECTED,
            event=HumanLoopProgressEventType.REVIEW_REJECTED,
            sequence=sequence + 1,
            timestamp=review.timestamp,
        )
        return self._snapshot(
            proposal=proposal,
            review=review,
            state=HumanLoopState.REJECTED,
            progress_sequence=sequence,
        )

    def project_feedback(
        self, request: FeedbackProjectionRequest
    ) -> FeedbackProjection:
        safe_request = _typed_copy(request, FeedbackProjectionRequest)
        if (
            safe_request.review.decision is not HumanReviewDecision.CHANGES_REQUESTED
            or safe_request.review.review_comment is None
        ):
            raise HumanLoopRejected("feedback projection is rejected")
        try:
            raw_feedback = self.__feedback_port.project(safe_request)
        except Exception:
            raise FeedbackProjectionUnavailable(
                "feedback projection is unavailable"
            ) from None
        feedback = _typed_copy(raw_feedback, FeedbackProjection)
        if (
            feedback.proposal_id != safe_request.review.proposal_id
            or feedback.review_fingerprint != safe_request.review.fingerprint
        ):
            raise HumanLoopRejected("feedback binding is invalid")
        return feedback

    def prepare_revision(self, request: RevisionPreparationRequest) -> RevisionProposal:
        safe_request = _typed_copy(request, RevisionPreparationRequest)
        self._validate_revision_request(safe_request)
        context_values = {
            "proposal_fingerprint": safe_request.proposal.fingerprint,
            "feedback_fingerprint": safe_request.feedback.fingerprint,
            "context_references": safe_request.context_references,
        }
        context = RevisionContext(
            **context_values,
            fingerprint=revision_context_fingerprint(**context_values),
        )
        generation_request = RevisionGenerationRequest(
            revision_id=safe_request.revision_id,
            base_proposal_id=safe_request.proposal.proposal_id,
            context=context,
            timestamp=safe_request.timestamp,
        )
        try:
            raw_revision = self.__proposal_port.prepare_revision(generation_request)
        except Exception:
            raise RevisionProposalUnavailable(
                "revision proposal is unavailable"
            ) from None
        revision = _typed_copy(raw_revision, RevisionProposal)
        if (
            revision.revision_id != safe_request.revision_id
            or revision.base_proposal_id != safe_request.proposal.proposal_id
        ):
            raise HumanLoopRejected("revision proposal binding is invalid")
        return revision

    @staticmethod
    def _validate_review(
        review: HumanReviewDecisionProjection,
        proposal: ProposalProjection,
        request: HumanReviewRequest,
    ) -> None:
        if (
            review.proposal_id != proposal.proposal_id
            or review.proposal_fingerprint != proposal.fingerprint
            or review.reviewer != request.reviewer
            or review.decision is not request.decision
            or review.review_comment != request.review_comment
            or review.timestamp != request.timestamp
        ):
            raise HumanLoopRejected("review binding is invalid")

    @staticmethod
    def _validate_revision_request(request: RevisionPreparationRequest) -> None:
        if request.review.decision is not HumanReviewDecision.CHANGES_REQUESTED:
            raise HumanLoopRejected("revision is not authorized")
        if (
            request.review.proposal_id != request.proposal.proposal_id
            or request.review.proposal_fingerprint != request.proposal.fingerprint
            or request.feedback.proposal_id != request.proposal.proposal_id
            or request.feedback.review_fingerprint != request.review.fingerprint
        ):
            raise HumanLoopRejected("revision binding is invalid")
        sources = {item.source_type for item in request.context_references}
        if sources != {
            RevisionContextSource.KNOWLEDGE_CONTEXT,
            RevisionContextSource.MEMORY_CONTEXT,
        }:
            raise HumanLoopRejected("revision context is incomplete")

    def _emit(
        self,
        *,
        proposal_id: str,
        state: HumanLoopState,
        event: HumanLoopProgressEventType,
        sequence: int,
        timestamp,
    ) -> int:
        progress = HumanLoopProgressEvent(
            sequence=sequence,
            proposal_id=proposal_id,
            state=state,
            event=event,
            timestamp=timestamp,
        )
        try:
            self.__progress_sink.emit(progress)
        except Exception:
            raise HumanLoopProgressUnavailable(
                "human loop progress is unavailable"
            ) from None
        return sequence

    @staticmethod
    def _snapshot(
        *,
        proposal: ProposalProjection,
        review: HumanReviewDecisionProjection,
        state: HumanLoopState,
        progress_sequence: int,
    ) -> HumanReviewSnapshot:
        values = {
            "proposal": proposal,
            "state": state,
            "review": review,
            "progress_sequence": progress_sequence,
        }
        return HumanReviewSnapshot(
            proposal_id=proposal.proposal_id,
            **values,
            fingerprint=human_review_snapshot_fingerprint(**values),
        )


def _create_human_loop_service(
    *,
    proposal_port: DesignProposalPort,
    review_port: HumanReviewPort,
    feedback_port: FeedbackProjectionPort,
    progress_sink: HumanLoopProgressSink,
) -> HumanLoopPort:
    return _HumanLoopService(
        proposal_port=proposal_port,
        review_port=review_port,
        feedback_port=feedback_port,
        progress_sink=progress_sink,
    )
