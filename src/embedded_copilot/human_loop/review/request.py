"""Safe metadata-only projection from an Engineering Generation proposal."""

from pydantic import ValidationError

from embedded_copilot.engineering_generation import ArtifactProposal
from embedded_copilot.human_loop.exceptions import HumanLoopRejected
from embedded_copilot.human_loop.models import (
    ProposalProjection,
    proposal_projection_fingerprint,
)


def project_proposal_projection(
    proposal: ArtifactProposal,
    *,
    proposal_id: str,
    artifact_version: int,
) -> ProposalProjection:
    """Project only review-safe metadata from a typed artifact proposal."""
    if type(proposal) is not ArtifactProposal:
        raise HumanLoopRejected("proposal is invalid")
    try:
        safe_proposal = ArtifactProposal.model_validate(proposal.model_copy(deep=True))
        reference_ids = tuple(
            sorted({reference.reference_id for reference in safe_proposal.references})
        )
        values = {
            "proposal_id": proposal_id,
            "artifact_type": safe_proposal.artifact_type,
            "artifact_version": artifact_version,
            "summary": safe_proposal.summary,
            "reference_ids": reference_ids,
        }
        return ProposalProjection(
            **values,
            fingerprint=proposal_projection_fingerprint(**values),
        )
    except (TypeError, ValueError, ValidationError):
        raise HumanLoopRejected("proposal is invalid") from None
