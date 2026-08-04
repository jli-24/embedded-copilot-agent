from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.hardware_observation.contracts import (
    BootStatus,
    HealthStatus,
    ObservationSnapshot,
    observation_snapshot_fingerprint,
)
from embedded_copilot.hardware_observation.adapters.fake import FakeObservationAdapter
from embedded_copilot.hardware_observation.adapters.serial import (
    SerialObservationAdapter,
)
from embedded_copilot.hardware_observation.exceptions import ObservationUnavailable


def test_observation_is_safe_and_deterministic() -> None:
    adapter = FakeObservationAdapter()
    values = tuple(adapter.read("board-1") for _ in range(100))
    assert len(set(values)) == 1
    snapshot = values[0]
    assert snapshot.fingerprint == observation_snapshot_fingerprint(snapshot)
    assert "raw_log" not in snapshot.model_dump()


def test_observation_rejects_sensitive_summary_and_serial_unavailable() -> None:
    with pytest.raises(ValidationError):
        ObservationSnapshot.create(
            device_id="board-1",
            boot_status=BootStatus.BOOTED,
            firmware_version="1.0",
            health_status=HealthStatus.HEALTHY,
            error_summary="token=secret",
        )
    with pytest.raises(ObservationUnavailable, match="OBSERVATION_UNAVAILABLE"):
        SerialObservationAdapter().read("board-1")
