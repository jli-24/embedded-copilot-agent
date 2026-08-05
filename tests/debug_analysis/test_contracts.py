from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.debug_analysis.adapters.fake import FakeDebugAnalysisPort
from embedded_copilot.debug_analysis.contracts import (
    DebugAnalysisSnapshot,
    DebugInputSnapshot,
)


def test_debug_snapshot_is_frozen_and_deterministic() -> None:
    port = FakeDebugAnalysisPort()
    values = [port.get_snapshot("demo") for _ in range(100)]
    assert len({item.fingerprint for item in values}) == 1
    with pytest.raises(ValidationError):
        values[0].project_id = "other"  # type: ignore[misc]


def test_debug_input_rejects_sensitive_projection() -> None:
    with pytest.raises(ValidationError):
        DebugInputSnapshot.create(
            project_id="demo",
            failure_reference="failure:demo",
            failure_type="BUILD",
            safe_summary="command: make",
            evidence_reference="evidence:demo",
        )


def test_snapshot_rejects_list_and_tampering() -> None:
    snapshot = FakeDebugAnalysisPort().get_snapshot("demo")
    with pytest.raises(ValidationError):
        DebugAnalysisSnapshot.model_validate(
            {**snapshot.model_dump(mode="python"), "findings": list(snapshot.findings)}
        )
    with pytest.raises(ValidationError):
        DebugAnalysisSnapshot.model_validate(
            {**snapshot.model_dump(mode="python"), "fingerprint": "sha256:" + "0" * 64}
        )
