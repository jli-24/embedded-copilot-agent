"""Composition root for the Human Loop Runtime."""

from embedded_copilot.human_loop.contracts import (
    DesignProposalPort,
    FeedbackProjectionPort,
    HumanLoopProgressSink,
    HumanReviewPort,
)
from embedded_copilot.human_loop.exceptions import HumanLoopRejected
from embedded_copilot.human_loop.facade import HumanLoopRuntime
from embedded_copilot.human_loop.runtime import _create_human_loop_service


def create_human_loop_runtime(
    *,
    proposal_port: DesignProposalPort,
    review_port: HumanReviewPort,
    feedback_port: FeedbackProjectionPort,
    progress_sink: HumanLoopProgressSink,
) -> HumanLoopRuntime:
    """Create a Human Loop Runtime from caller-owned Protocols."""
    if not isinstance(proposal_port, DesignProposalPort):
        raise HumanLoopRejected("proposal port is invalid")
    if not isinstance(review_port, HumanReviewPort):
        raise HumanLoopRejected("review port is invalid")
    if not isinstance(feedback_port, FeedbackProjectionPort):
        raise HumanLoopRejected("feedback port is invalid")
    if not isinstance(progress_sink, HumanLoopProgressSink):
        raise HumanLoopRejected("progress sink is invalid")
    return HumanLoopRuntime._compose(
        _create_human_loop_service(
            proposal_port=proposal_port,
            review_port=review_port,
            feedback_port=feedback_port,
            progress_sink=progress_sink,
        )
    )
