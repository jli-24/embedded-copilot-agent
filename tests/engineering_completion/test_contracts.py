from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_completion.adapters.fake import (
    FakeEngineeringCompletionPort,
)
from embedded_copilot.engineering_completion.contracts import (
    EngineeringCompletionSnapshot,
    ValidationReason,
)


def test_fake_snapshot_is_deterministic_and_frozen() -> None:
    port = FakeEngineeringCompletionPort()
    snapshots = [port.get_snapshot("demo") for _ in range(100)]
    assert len({item.fingerprint for item in snapshots}) == 1
    with pytest.raises((ValidationError, TypeError)):
        snapshots[0].project_id = "other"  # type: ignore[misc]
    assert "reason" not in snapshots[0].model_dump()


def test_snapshot_rejects_tampering_and_extra_fields() -> None:
    snapshot = FakeEngineeringCompletionPort().get_snapshot("demo")
    with pytest.raises(ValueError):
        EngineeringCompletionSnapshot.model_validate(
            {**snapshot.model_dump(mode="python"), "fingerprint": "sha256:" + "0" * 64}
        )
    with pytest.raises(ValueError):
        EngineeringCompletionSnapshot.model_validate(
            {**snapshot.model_dump(mode="python"), "unexpected": "x"}
        )


def test_internal_validation_reason_is_enum_only() -> None:
    assert ValidationReason.PROJECT_MISMATCH.value == "PROJECT_MISMATCH"
