from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_feedback import (
    EngineeringFeedbackRequest,
    FeedbackItemType,
    RequestChangeFeedbackItem,
    create_engineering_feedback_runtime,
    engineering_feedback_request_fingerprint,
)
from tests.engineering_feedback.conftest import (
    NOW,
    artifact_fingerprint,
    make_change_item,
    make_simple_item,
)


def make_request(contract, items, *, execution=None, validation=None):
    values = dict(
        feedback_id="feedback-1",
        artifact_contract=contract,
        execution_report=execution,
        validation_report=validation,
        feedback_items=items,
        submitted_at=NOW,
    )
    return EngineeringFeedbackRequest(
        **values,
        fingerprint=engineering_feedback_request_fingerprint(**values),
    )


def test_factory_exposes_only_feedback_port() -> None:
    runtime = create_engineering_feedback_runtime()
    assert callable(runtime.engineering_feedback_port)
    assert set(name for name in dir(runtime) if not name.startswith("_")) == {
        "engineering_feedback_port"
    }


def test_contracts_are_frozen_strict_and_tuple_only(feedback_sources) -> None:
    contract, _, _ = feedback_sources
    target = artifact_fingerprint(contract)
    item = make_change_item(target)
    request = make_request(contract, (item,))

    with pytest.raises(ValidationError):
        item.reason = "changed"
    with pytest.raises(ValidationError):
        RequestChangeFeedbackItem.model_validate(
            {**item.model_dump(mode="python"), "constraints": ["POWER_LIMIT"]}
        )
    with pytest.raises(ValidationError):
        EngineeringFeedbackRequest.model_validate(
            {**request.model_dump(mode="python"), "unexpected": "forbidden"}
        )
    with pytest.raises(ValidationError):
        EngineeringFeedbackRequest.model_validate(
            {**request.model_dump(mode="python"), "submitted_at": datetime(2026, 8, 9)}
        )


def test_item_and_request_fingerprints_reject_tampering(feedback_sources) -> None:
    contract, _, _ = feedback_sources
    item = make_change_item(artifact_fingerprint(contract))
    with pytest.raises(ValidationError):
        RequestChangeFeedbackItem.model_validate(
            {**item.model_dump(mode="python"), "fingerprint": "sha256:" + "0" * 64}
        )
    request = make_request(contract, (item,))
    with pytest.raises(ValidationError):
        EngineeringFeedbackRequest.model_validate(
            {**request.model_dump(mode="python"), "fingerprint": "sha256:" + "0" * 64}
        )


def test_feedback_items_are_uniform_sorted_and_target_bound(feedback_sources) -> None:
    contract, _, _ = feedback_sources
    target = artifact_fingerprint(contract)
    first = make_change_item(target, change_id="change-1", revision_id="revision-1")
    second = make_change_item(target, change_id="change-2", revision_id="revision-2")
    make_request(contract, (first, second))

    with pytest.raises(ValidationError):
        make_request(contract, (second, first))
    with pytest.raises(ValidationError):
        make_request(
            contract,
            (first, make_simple_item(FeedbackItemType.COMMENT, target)),
        )


def test_optional_reports_must_bind_to_artifact_sources(feedback_sources) -> None:
    contract, execution, validation = feedback_sources
    target = artifact_fingerprint(contract)
    item = make_simple_item(FeedbackItemType.COMMENT, target)
    request = make_request(
        contract,
        (item,),
        execution=execution,
        validation=validation,
    )
    assert request.execution_report is not execution
    assert request.validation_report is not validation
    assert request.execution_report == execution
    assert request.validation_report == validation
    source_fingerprints = {
        source.source_fingerprint
        for binding in contract.source_bindings
        for source in binding.sources
    }
    assert execution.artifact_fingerprint == contract.fingerprint
    assert (
        execution.execution_contract.artifact_source_fingerprint
        == contract.artifact_source_fingerprint
    )
    assert {
        validation.requirement_fingerprint,
        validation.context_fingerprint,
        validation.hardware_proposal_fingerprint,
        validation.firmware_proposal_fingerprint,
    }.issubset(source_fingerprints)
