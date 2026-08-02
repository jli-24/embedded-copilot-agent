"""Framework-independent, proposal-only Engineering Feedback Layer."""

from embedded_copilot.engineering_feedback.contracts import EngineeringFeedbackPort
from embedded_copilot.engineering_feedback.exceptions import (
    EngineeringFeedbackError,
    EngineeringFeedbackRejected,
)
from embedded_copilot.engineering_feedback.facade import EngineeringFeedbackRuntime
from embedded_copilot.engineering_feedback.factory import (
    create_engineering_feedback_runtime,
)
from embedded_copilot.engineering_feedback.integration.inputs import (
    EngineeringFeedbackRequest,
    engineering_feedback_request_fingerprint,
)
from embedded_copilot.engineering_feedback.models import (
    ApproveFeedbackItem,
    CommentFeedbackItem,
    EngineeringChangeRequest,
    EngineeringChangeType,
    EngineeringFeedbackProjection,
    EngineeringFeedbackReport,
    EngineeringFeedbackReviewProjection,
    EngineeringRevisionProposal,
    FeedbackFindingCode,
    FeedbackItem,
    FeedbackItemType,
    FeedbackReviewOutcome,
    FeedbackTargetDomain,
    RejectFeedbackItem,
    RequestChangeFeedbackItem,
    RevisionProposalState,
    canonical_feedback_json,
    engineering_change_request_fingerprint,
    engineering_feedback_projection_fingerprint,
    engineering_feedback_report_fingerprint,
    engineering_feedback_review_fingerprint,
    engineering_revision_proposal_fingerprint,
    feedback_item_fingerprint,
)

__all__ = (
    "ApproveFeedbackItem",
    "CommentFeedbackItem",
    "EngineeringChangeRequest",
    "EngineeringChangeType",
    "EngineeringFeedbackError",
    "EngineeringFeedbackPort",
    "EngineeringFeedbackProjection",
    "EngineeringFeedbackRejected",
    "EngineeringFeedbackReport",
    "EngineeringFeedbackRequest",
    "EngineeringFeedbackReviewProjection",
    "EngineeringFeedbackRuntime",
    "EngineeringRevisionProposal",
    "FeedbackFindingCode",
    "FeedbackItem",
    "FeedbackItemType",
    "FeedbackReviewOutcome",
    "FeedbackTargetDomain",
    "RejectFeedbackItem",
    "RequestChangeFeedbackItem",
    "RevisionProposalState",
    "canonical_feedback_json",
    "create_engineering_feedback_runtime",
    "engineering_change_request_fingerprint",
    "engineering_feedback_projection_fingerprint",
    "engineering_feedback_report_fingerprint",
    "engineering_feedback_request_fingerprint",
    "engineering_feedback_review_fingerprint",
    "engineering_revision_proposal_fingerprint",
    "feedback_item_fingerprint",
)
