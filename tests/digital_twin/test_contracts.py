from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.digital_twin.adapters.fake import FakeDigitalTwinAdapter
from embedded_copilot.digital_twin.contracts import DigitalTwinSnapshot


def test_fake_twin_is_deterministic_and_safe() -> None:
    values = [FakeDigitalTwinAdapter().get_snapshot("demo") for _ in range(100)]
    assert len({value.fingerprint for value in values}) == 1
    assert values[0].project_id == "demo"
    assert "stdout" not in values[0].model_dump_json().lower()


def test_twin_is_frozen_tuple_only_and_tamper_checked() -> None:
    snapshot = FakeDigitalTwinAdapter().get_snapshot("demo")
    with pytest.raises(ValidationError):
        snapshot.project_id = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        DigitalTwinSnapshot.model_validate(
            {**snapshot.model_dump(mode="python"), "metrics": [snapshot.metrics]}
        )
    with pytest.raises(ValidationError):
        DigitalTwinSnapshot.model_validate(
            {**snapshot.model_dump(mode="python"), "fingerprint": "sha256:" + "0" * 64}
        )
