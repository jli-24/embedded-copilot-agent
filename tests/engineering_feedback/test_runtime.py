from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_artifacts import ArtifactType
from embedded_copilot.engineering_feedback import (
    EngineeringFeedbackRejected,
    FeedbackFindingCode,
    FeedbackItemType,
    FeedbackReviewOutcome,
    FeedbackTargetDomain,
    RevisionProposalState,
    create_engineering_feedback_runtime,
)
from tests.engineering_feedback.conftest import (
    artifact_fingerprint,
    make_change_item,
    make_simple_item,
)
from tests.engineering_feedback.test_contracts import make_request


@pytest.mark.parametrize(
    ("item_type", "outcome", "finding"),
    (
        (
            FeedbackItemType.APPROVE,
            FeedbackReviewOutcome.APPROVED,
            FeedbackFindingCode.CURRENT_RESULT_APPROVED,
        ),
        (
            FeedbackItemType.REJECT,
            FeedbackReviewOutcome.REJECTED,
            FeedbackFindingCode.CURRENT_RESULT_REJECTED,
        ),
        (
            FeedbackItemType.COMMENT,
            FeedbackReviewOutcome.COMMENT_RECORDED,
            FeedbackFindingCode.COMMENT_RECORDED,
        ),
    ),
)
def test_non_change_feedback_is_projection_only(
    feedback_sources, item_type, outcome, finding
) -> None:
    contract, execution, validation = feedback_sources
    item = make_simple_item(item_type, contract.fingerprint)
    request = make_request(
        contract,
        (item,),
        execution=execution,
        validation=validation,
    )
    before = request.model_dump(mode="json")

    report = (
        create_engineering_feedback_runtime()
        .engineering_feedback_port()
        .submit_feedback(request)
    )

    assert report.feedback.items == (item,)
    assert report.change_requests == ()
    assert report.revision_proposals == ()
    assert report.review.outcome is outcome
    assert finding in report.review.finding_codes
    assert report.feedback.execution_report_fingerprint == execution.fingerprint
    assert report.feedback.validation_report_fingerprint == validation.fingerprint
    assert report.candidate_semantics == "unverified"
    assert report.review_required is True
    assert request.model_dump(mode="json") == before


def test_request_change_creates_bound_change_and_revision_without_mutation(
    feedback_sources,
) -> None:
    contract, _, _ = feedback_sources
    target = artifact_fingerprint(contract, ArtifactType.HARDWARE_MODEL)
    item = make_change_item(
        target,
        target_domain=FeedbackTargetDomain.HARDWARE,
    )
    request = make_request(contract, (item,))
    before_contract = contract.model_dump(mode="json")

    report = (
        create_engineering_feedback_runtime()
        .engineering_feedback_port()
        .submit_feedback(request)
    )

    change = report.change_requests[0]
    revision = report.revision_proposals[0]
    assert change.change_id == item.change_id
    assert change.target_domain is item.target_domain
    assert change.target_artifact_fingerprint == target
    assert change.reason == item.reason
    assert change.constraints == item.constraints
    assert revision.revision_id == item.revision_id
    assert revision.base_artifact_fingerprint == target
    assert revision.change_request_fingerprint == change.fingerprint
    assert revision.affected_domains == (FeedbackTargetDomain.HARDWARE,)
    assert revision.state is RevisionProposalState.PROPOSED
    assert revision.review_required is True
    assert report.review.outcome is FeedbackReviewOutcome.CHANGES_PROPOSED
    assert contract.model_dump(mode="json") == before_contract


def test_invalid_target_and_cross_domain_target_are_rejected(feedback_sources) -> None:
    contract, _, _ = feedback_sources
    invalid = make_change_item("sha256:" + "0" * 64)
    with pytest.raises(
        EngineeringFeedbackRejected, match="feedback request is invalid"
    ):
        create_engineering_feedback_runtime().engineering_feedback_port().submit_feedback(
            make_request(contract, (invalid,))
        )

    hardware = artifact_fingerprint(contract, ArtifactType.HARDWARE_MODEL)
    wrong_domain = make_change_item(
        hardware,
        target_domain=FeedbackTargetDomain.FIRMWARE,
    )
    with pytest.raises(
        EngineeringFeedbackRejected, match="feedback request is invalid"
    ):
        create_engineering_feedback_runtime().engineering_feedback_port().submit_feedback(
            make_request(contract, (wrong_domain,))
        )


def test_request_change_ids_are_unique(feedback_sources) -> None:
    contract, _, _ = feedback_sources
    target = artifact_fingerprint(contract)
    first = make_change_item(target, change_id="change-1", revision_id="revision-1")
    duplicate = make_change_item(
        target,
        change_id="change-1",
        revision_id="revision-2",
        reason="A second requested change.",
    )
    with pytest.raises(ValidationError):
        make_request(contract, (first, duplicate))
