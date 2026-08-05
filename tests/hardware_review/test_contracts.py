import pytest
from pydantic import ValidationError

from embedded_copilot.hardware_review.contracts import (
    HardwareReviewCategory,
    HardwareReviewProposal,
    HardwareReviewSeverity,
    HardwareReviewStatus,
    validate_review_proposals,
)


def proposal() -> HardwareReviewProposal:
    return HardwareReviewProposal.create(
        review_id="review:demo:component:1",
        project_id="demo",
        category=HardwareReviewCategory.COMPONENT,
        severity=HardwareReviewSeverity.MEDIUM,
        summary="Component identity requires review.",
        evidence_reference="design:demo",
        status=HardwareReviewStatus.PROJECTED,
    )


def test_review_proposal_is_frozen_and_binding_checked() -> None:
    value = proposal()
    assert validate_review_proposals((value,)) == (value,)
    with pytest.raises(ValidationError):
        HardwareReviewProposal.model_validate(
            {**value.model_dump(), "fingerprint": "sha256:" + "0" * 64}
        )
    with pytest.raises(TypeError):
        validate_review_proposals([value])
