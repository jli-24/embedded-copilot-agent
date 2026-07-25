from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from embedded_copilot.experience.models import (
    BlueprintEdge,
    BlueprintNode,
    BlueprintProjection,
    ExperienceRequest,
    ExperienceResponse,
    ReviewIntent,
    ReviewIntentAction,
    ViewerState,
    ViewerStatus,
)

UTC = timezone.utc
CREATED = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)


def test_experience_response_requires_session_identity() -> None:
    response = ExperienceResponse(
        session_id="session:1",
        project_summary="ESP32 security terminal.",
        artifact_ids=("artifact:1",),
        file_count=2,
        message_count=3,
        progress_count=1,
        viewer_state=ViewerState(status=ViewerStatus.READY),
    )

    assert response.session_id == "session:1"
    with pytest.raises(ValidationError):
        ExperienceResponse.model_validate(
            {
                key: value
                for key, value in response.model_dump(mode="python").items()
                if key != "session_id"
            }
        )


def test_experience_contracts_reject_engineering_owned_fields() -> None:
    payload = ExperienceRequest(session_id="session:1").model_dump(mode="python")

    for forbidden in (
        "gpio",
        "component",
        "components",
        "connection",
        "connections",
        "voltage",
        "current",
        "artifact_update",
    ):
        with pytest.raises(ValidationError):
            ExperienceRequest.model_validate({**payload, forbidden: "unsafe"})


def test_review_intent_is_user_source_metadata_only() -> None:
    intent = ReviewIntent(
        intent_id="review:1",
        session_id="session:1",
        artifact_id="artifact:1",
        action=ReviewIntentAction.APPROVE_INTENT,
        comment_summary="Record approval intent for Engineering Agent review.",
        timestamp=CREATED,
    )

    assert intent.source == "user"
    assert "timestamp" in ReviewIntent.model_fields
    assert "created_at" not in ReviewIntent.model_fields
    assert "approval_status" not in ReviewIntent.model_fields
    assert "ApprovalEvent" not in intent.model_dump_json()

    with pytest.raises(ValidationError):
        ReviewIntent.model_validate(
            {
                **intent.model_dump(mode="python"),
                "source": "model",
            }
        )


def test_blueprint_projection_rejects_unbound_edges() -> None:
    node = BlueprintNode(node_id="node:esp32", label="ESP32-S3", kind="module")
    edge = BlueprintEdge(
        edge_id="edge:1",
        source_node_id=node.node_id,
        target_node_id="node:missing",
        label="Existing relationship",
    )

    with pytest.raises(ValidationError, match="unresolved"):
        BlueprintProjection(
            session_id="session:1",
            artifact_id="artifact:1",
            nodes=(node,),
            edges=(edge,),
        )
