from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_events import (
    EngineeringEvent,
    EngineeringEventType,
    canonical_event_json,
    engineering_event_fingerprint,
)


def _event(**overrides: object) -> EngineeringEvent:
    values: dict[str, object] = {
        "sequence": 1,
        "event_type": EngineeringEventType.AGENT_STARTED,
        "stage": "ENGINEERING_CHAT",
        "status": "STARTED",
        "count": 0,
        "reference_id": "chat-request-1",
        "timestamp": datetime(2026, 8, 12, 8, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return EngineeringEvent(
        **values,
        fingerprint=engineering_event_fingerprint(**values),
    )


def test_event_contract_is_frozen_strict_and_normalizes_utc() -> None:
    event = _event(
        timestamp=datetime(
            2026,
            8,
            12,
            16,
            0,
            tzinfo=timezone(timedelta(hours=8)),
        )
    )

    assert event.timestamp == datetime(2026, 8, 12, 8, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        event.sequence = 2  # type: ignore[misc]
    with pytest.raises(ValidationError):
        EngineeringEvent.model_validate(
            {**event.model_dump(), "unexpected": "payload"}
        )
    with pytest.raises(ValidationError):
        _event(sequence="1")


def test_event_fingerprint_and_serialization_are_deterministic() -> None:
    first = _event()
    second = _event()

    assert first == second
    assert hash(first) == hash(second)
    assert first.fingerprint == second.fingerprint
    assert canonical_event_json(first) == canonical_event_json(second)


def test_event_rejects_tampering_and_sensitive_fields() -> None:
    event = _event()

    with pytest.raises(ValidationError):
        EngineeringEvent.model_validate(
            event.model_copy(update={"stage": "MODEL_PROVIDER"})
        )
    with pytest.raises(ValidationError):
        EngineeringEvent.model_validate(
            {
                **event.model_dump(),
                "provider_error": "api_key=secret",
            }
        )
