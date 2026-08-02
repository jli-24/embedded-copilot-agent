"""Typed Human Loop to UI projection adapter."""

from __future__ import annotations

from embedded_copilot.human_loop import HumanLoopProgressEvent, HumanReviewSnapshot

from embedded_copilot.engineering_interface.exceptions import (
    EngineeringInterfaceRejected,
)
from embedded_copilot.engineering_interface.models import (
    EngineeringProgressEvent,
    EngineeringProgressSource,
    HumanReviewUIProjection,
    make_human_review_projection,
    make_progress_event,
)


def project_human_progress(
    *,
    session_id: str,
    sequence: int,
    event: object,
) -> EngineeringProgressEvent:
    try:
        if type(event) is not HumanLoopProgressEvent:
            raise TypeError("invalid human progress")
        copied = event.model_copy(deep=True)
        checked = HumanLoopProgressEvent.model_validate(copied)
        return make_progress_event(
            sequence=sequence,
            session_id=session_id,
            source=EngineeringProgressSource.HUMAN_LOOP,
            source_reference_id=checked.proposal_id,
            source_sequence=checked.sequence,
            event=checked.event.value,
            state=checked.state.value,
            count=0,
            timestamp=checked.timestamp,
        )
    except Exception:
        raise EngineeringInterfaceRejected("interface request rejected") from None


def project_human_review(event: object) -> HumanReviewUIProjection:
    try:
        if type(event) is not HumanReviewSnapshot:
            raise TypeError("invalid human review")
        copied = event.model_copy(deep=True)
        checked = HumanReviewSnapshot.model_validate(copied)
        return make_human_review_projection(
            proposal_id=checked.proposal_id,
            artifact_type=checked.proposal.artifact_type.value,
            artifact_version=checked.proposal.artifact_version,
            summary=checked.proposal.summary,
            reference_ids=checked.proposal.reference_ids,
            state=checked.state.value,
            decision=checked.review.decision.value,
            reviewer=checked.review.reviewer,
            reviewed_at=checked.review.timestamp,
            source_snapshot_fingerprint=checked.fingerprint,
        )
    except Exception:
        raise EngineeringInterfaceRejected("interface request rejected") from None
