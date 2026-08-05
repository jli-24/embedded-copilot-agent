from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_optimization.adapters.fake import (
    FakeOptimizationAnalysisPort,
)
from embedded_copilot.engineering_optimization.contracts import (
    OptimizationConfidence,
    OptimizationFinding,
)


def test_analysis_is_deterministic_and_findings_are_safe() -> None:
    values = [FakeOptimizationAnalysisPort().get_snapshot("demo") for _ in range(100)]
    assert len({value.fingerprint for value in values}) == 1
    assert values[0].findings[0].confidence is OptimizationConfidence.PROJECTED


def test_finding_is_frozen_and_tamper_checked() -> None:
    finding = FakeOptimizationAnalysisPort().get_snapshot("demo").findings[0]
    with pytest.raises(ValidationError):
        finding.status = "APPROVED"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        OptimizationFinding.model_validate(
            {**finding.model_dump(mode="python"), "fingerprint": "sha256:" + "0" * 64}
        )
