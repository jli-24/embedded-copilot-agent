"""Deterministic, proposal-only Engineering Feedback projection."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.engineering_feedback.contracts import EngineeringFeedbackPort
from embedded_copilot.engineering_feedback.exceptions import EngineeringFeedbackRejected
from embedded_copilot.engineering_feedback.integration.inputs import (
    EngineeringFeedbackRequest,
    project_request,
)
from embedded_copilot.engineering_feedback.models import (
    EngineeringChangeRequest,
    EngineeringFeedbackProjection,
    EngineeringFeedbackReport,
    EngineeringFeedbackReviewProjection,
    EngineeringRevisionProposal,
    FeedbackFindingCode,
    FeedbackItemType,
    FeedbackReviewOutcome,
    RequestChangeFeedbackItem,
    RevisionProposalState,
    engineering_change_request_fingerprint,
    engineering_feedback_projection_fingerprint,
    engineering_feedback_report_fingerprint,
    engineering_feedback_review_fingerprint,
    engineering_revision_proposal_fingerprint,
)


class _EngineeringFeedbackService(EngineeringFeedbackPort):
    __slots__ = ()

    def submit_feedback(
        self,
        request: EngineeringFeedbackRequest,
    ) -> EngineeringFeedbackReport:
        try:
            projected = project_request(request)
            safe = projected.request
            feedback_values = dict(
                feedback_id=safe.feedback_id,
                artifact_contract_fingerprint=safe.artifact_contract.fingerprint,
                artifact_source_fingerprint=(
                    safe.artifact_contract.artifact_source_fingerprint
                ),
                execution_report_fingerprint=projected.execution_report_fingerprint,
                validation_report_fingerprint=projected.validation_report_fingerprint,
                items=safe.feedback_items,
                submitted_at=safe.submitted_at,
            )
            feedback = EngineeringFeedbackProjection(
                **feedback_values,
                fingerprint=engineering_feedback_projection_fingerprint(
                    **feedback_values
                ),
            )
            changes, revisions = self._project_changes(safe.feedback_items)
            item_type = safe.feedback_items[0].type
            outcome, findings = _review_semantics(item_type)
            review_values = dict(
                feedback_id=safe.feedback_id,
                outcome=outcome,
                item_count=len(safe.feedback_items),
                change_request_count=len(changes),
                revision_proposal_count=len(revisions),
                execution_report_fingerprint=projected.execution_report_fingerprint,
                validation_report_fingerprint=projected.validation_report_fingerprint,
                finding_codes=findings,
                review_required=True,
            )
            review = EngineeringFeedbackReviewProjection(
                **review_values,
                fingerprint=engineering_feedback_review_fingerprint(**review_values),
            )
            report_values = dict(
                feedback=feedback,
                change_requests=changes,
                revision_proposals=revisions,
                review=review,
                candidate_semantics="unverified",
                review_required=True,
            )
            return EngineeringFeedbackReport(
                **report_values,
                fingerprint=engineering_feedback_report_fingerprint(**report_values),
            )
        except EngineeringFeedbackRejected:
            raise
        except (TypeError, ValueError, ValidationError):
            raise EngineeringFeedbackRejected("feedback request is invalid") from None

    @staticmethod
    def _project_changes(
        items: tuple,
    ) -> tuple[
        tuple[EngineeringChangeRequest, ...],
        tuple[EngineeringRevisionProposal, ...],
    ]:
        changes = []
        revisions = []
        for item in items:
            if not isinstance(item, RequestChangeFeedbackItem):
                continue
            change_values = dict(
                change_id=item.change_id,
                target_domain=item.target_domain,
                target_artifact_fingerprint=item.target_reference,
                change_type=item.change_type,
                reason=item.reason,
                constraints=item.constraints,
            )
            change = EngineeringChangeRequest(
                **change_values,
                fingerprint=engineering_change_request_fingerprint(**change_values),
            )
            revision_values = dict(
                revision_id=item.revision_id,
                state=RevisionProposalState.PROPOSED,
                base_artifact_fingerprint=item.target_reference,
                change_request_fingerprint=change.fingerprint,
                affected_domains=(item.target_domain,),
                review_required=True,
            )
            revision = EngineeringRevisionProposal(
                **revision_values,
                fingerprint=engineering_revision_proposal_fingerprint(
                    **revision_values
                ),
            )
            changes.append(change)
            revisions.append(revision)
        return (
            tuple(sorted(changes, key=lambda item: item.change_id)),
            tuple(sorted(revisions, key=lambda item: item.revision_id)),
        )


def _review_semantics(
    item_type: FeedbackItemType,
) -> tuple[FeedbackReviewOutcome, tuple[FeedbackFindingCode, ...]]:
    return {
        FeedbackItemType.APPROVE: (
            FeedbackReviewOutcome.APPROVED,
            (FeedbackFindingCode.CURRENT_RESULT_APPROVED,),
        ),
        FeedbackItemType.REJECT: (
            FeedbackReviewOutcome.REJECTED,
            (FeedbackFindingCode.CURRENT_RESULT_REJECTED,),
        ),
        FeedbackItemType.COMMENT: (
            FeedbackReviewOutcome.COMMENT_RECORDED,
            (FeedbackFindingCode.COMMENT_RECORDED,),
        ),
        FeedbackItemType.REQUEST_CHANGE: (
            FeedbackReviewOutcome.CHANGES_PROPOSED,
            (
                FeedbackFindingCode.CHANGE_REQUESTED,
                FeedbackFindingCode.REVISION_REVIEW_REQUIRED,
            ),
        ),
    }[item_type]


def _create_engineering_feedback_service() -> EngineeringFeedbackPort:
    return _EngineeringFeedbackService()
