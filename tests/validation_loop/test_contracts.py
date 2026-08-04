from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.validation_loop.contracts import (
    FlashState,
    LoopState,
    ObservationState,
    ValidationSnapshot,
    VerificationState,
    validation_snapshot_fingerprint,
)


def test_validation_snapshot_is_deterministic_and_frozen() -> None:
    snapshot = ValidationSnapshot.create(
        project_id="demo",
        firmware_reference="artifact-1",
        device_reference="board-1",
        build_status=LoopState.BUILD_READY,
        flash_status=FlashState.PENDING,
        observation_status=ObservationState.PENDING,
        verification_status=VerificationState.REVIEW_REQUIRED,
    )
    assert snapshot.fingerprint == validation_snapshot_fingerprint(snapshot)
    with pytest.raises(ValidationError):
        snapshot.project_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ValidationSnapshot.model_validate({**snapshot.model_dump(), "finding": "raw"})
