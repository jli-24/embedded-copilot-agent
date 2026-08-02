from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.engineering_artifacts import ArtifactType
from embedded_copilot.engineering_execution import (
    create_engineering_execution_runtime,
)
from embedded_copilot.engineering_feedback import (
    ApproveFeedbackItem,
    CommentFeedbackItem,
    EngineeringChangeType,
    FeedbackItemType,
    FeedbackTargetDomain,
    RejectFeedbackItem,
    RequestChangeFeedbackItem,
    feedback_item_fingerprint,
)
from tests.engineering_execution import conftest as _execution_fixtures

artifact_report = _execution_fixtures.artifact_report
firmware_request = _execution_fixtures.firmware_request
generation_request = _execution_fixtures.generation_request
validation_setup = _execution_fixtures.validation_setup

NOW = datetime(2026, 8, 9, 9, 0, tzinfo=UTC)


@pytest.fixture
def feedback_sources(artifact_report, generation_request):
    execution = (
        create_engineering_execution_runtime()
        .engineering_execution_port()
        .execute(_execution_fixtures.make_request(artifact_report))
    )
    return (
        artifact_report.artifact_contract,
        execution,
        generation_request.validation_report,
    )


def artifact_fingerprint(contract, artifact_type=ArtifactType.FIRMWARE_STRUCTURE):
    return next(
        item.artifact_fingerprint
        for item in contract.artifacts
        if item.artifact_type is artifact_type
    )


def make_simple_item(
    item_type, target_reference, *, reason="Engineering review recorded."
):
    cls = {
        FeedbackItemType.APPROVE: ApproveFeedbackItem,
        FeedbackItemType.REJECT: RejectFeedbackItem,
        FeedbackItemType.COMMENT: CommentFeedbackItem,
    }[item_type]
    values = dict(
        type=item_type,
        target_reference=target_reference,
        reason=reason,
        constraints=(),
    )
    return cls(**values, fingerprint=feedback_item_fingerprint(**values))


def make_change_item(
    target_reference,
    *,
    change_id="change-1",
    revision_id="revision-1",
    target_domain=FeedbackTargetDomain.FIRMWARE,
    change_type=EngineeringChangeType.MODIFY_CONSTRAINT,
    reason="Reduce the approved engineering power limit.",
    constraints=("POWER_LIMIT",),
):
    values = dict(
        type=FeedbackItemType.REQUEST_CHANGE,
        target_reference=target_reference,
        reason=reason,
        constraints=constraints,
        change_id=change_id,
        revision_id=revision_id,
        target_domain=target_domain,
        change_type=change_type,
    )
    return RequestChangeFeedbackItem(
        **values,
        fingerprint=feedback_item_fingerprint(**values),
    )
