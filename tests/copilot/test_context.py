from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from embedded_copilot.copilot.context import DesignSessionContext
from embedded_copilot.copilot.models import DesignStage, SessionApprovalStatus

UTC = timezone.utc


def _context(**updates: object) -> DesignSessionContext:
    payload: dict[str, object] = {
        "session_id": "session-1",
        "project_name": "Security Terminal",
        "user_requirement": "Review the existing embedded engineering design.",
        "current_stage": DesignStage.REQUIREMENT_ANALYSIS,
        "artifact_ids": ("artifact:1",),
        "decision_ids": ("decision:1",),
        "file_ids": ("file:1",),
        "approval_status": SessionApprovalStatus.PROPOSED,
        "created_at": datetime(2026, 7, 26, 8, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 7, 26, 8, 5, tzinfo=UTC),
    }
    payload.update(updates)
    return DesignSessionContext.model_validate(payload)


def test_session_context_is_frozen_deeply_immutable_and_deterministic() -> None:
    context = _context(
        artifact_ids=["artifact:1", "artifact:2"],
        decision_ids=["decision:1"],
        file_ids=["file:1"],
    )
    restored = DesignSessionContext.model_validate_json(context.model_dump_json())

    assert context.artifact_ids == ("artifact:1", "artifact:2")
    assert isinstance(context.artifact_ids, tuple)
    assert restored == context
    assert restored.model_dump_json() == context.model_dump_json()
    with pytest.raises(ValidationError):
        context.current_stage = DesignStage.REPORT  # type: ignore[misc]


@pytest.mark.parametrize(
    "updates",
    (
        {"created_at": datetime(2026, 7, 26, 8, 0)},
        {
            "created_at": datetime(
                2026, 7, 26, 9, 0, tzinfo=timezone(timedelta(hours=1))
            )
        },
        {"updated_at": datetime(2026, 7, 26, 7, 59, tzinfo=UTC)},
        {"artifact_ids": ("artifact:1", "ARTIFACT:1")},
        {"user_requirement": "first line\nsecond line"},
        {"project_name": r"C:\Users\private\project"},
        {"user_requirement": b"binary requirement"},
    ),
)
def test_session_context_rejects_unsafe_or_ambiguous_values(
    updates: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        _context(**updates)


def test_session_context_forbids_domain_objects_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _context(hardware_component="MQ-2")
    with pytest.raises(ValidationError):
        _context(artifact={"raw": "forbidden"})
