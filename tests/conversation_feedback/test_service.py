from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.conversation_feedback import (
    FeedbackRejected,
    FeedbackType,
    UserFeedback,
    canonical_feedback_json,
    create_conversation_feedback_service,
    user_feedback_fingerprint,
)
from embedded_copilot.engineering_events import EngineeringEventType


def _feedback(**overrides: object) -> UserFeedback:
    values: dict[str, object] = {
        "feedback_id": "feedback-1",
        "session_id": "session-1",
        "target_agent": "ENGINEERING_CHAT",
        "feedback_type": FeedbackType.CORRECT,
        "message": "Prefer the verified ESP32-S3 interface evidence.",
        "timestamp": datetime(2026, 8, 12, 8, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return UserFeedback(
        **values,
        fingerprint=user_feedback_fingerprint(**values),
    )


@pytest.mark.parametrize("feedback_type", tuple(FeedbackType))
def test_feedback_types_project_to_safe_event(feedback_type: FeedbackType) -> None:
    service = create_conversation_feedback_service().feedback_port()

    result = service.project(_feedback(feedback_type=feedback_type))

    assert result.feedback_type is feedback_type
    assert result.event.event_type is EngineeringEventType.USER_FEEDBACK
    assert result.event.reference_id == "feedback-1"
    assert set(result.model_dump()).isdisjoint({"message", "payload", "prompt"})


def test_feedback_is_frozen_strict_and_deterministic() -> None:
    feedback = _feedback()
    before = feedback.model_dump(mode="json")
    service = create_conversation_feedback_service().feedback_port()

    results = tuple(service.project(feedback) for _ in range(100))

    assert all(result == results[0] for result in results)
    assert len({result.fingerprint for result in results}) == 1
    assert len({hash(result) for result in results}) == 1
    assert len({canonical_feedback_json(result) for result in results}) == 1
    assert feedback.model_dump(mode="json") == before
    with pytest.raises(ValidationError):
        feedback.message = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        _feedback(feedback_type="APPROVE")


def test_feedback_revalidation_rejects_tampering_without_leaking_input() -> None:
    service = create_conversation_feedback_service().feedback_port()
    tampered = _feedback().model_copy(update={"message": "api_key=secret"})

    with pytest.raises(FeedbackRejected) as captured:
        service.project(tampered)

    assert str(captured.value) == "feedback request was rejected"
    assert "secret" not in str(captured.value)

