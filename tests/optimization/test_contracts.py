from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.optimization.adapters.fake import FakeOptimizationPort
from embedded_copilot.optimization.contracts import (
    OptimizationConfidence,
    OptimizationProposal,
)


def test_fake_proposal_is_deterministic_and_has_confidence() -> None:
    values = [FakeOptimizationPort().get_snapshot("demo") for _ in range(100)]
    assert all(item is not None for item in values)
    assert len({item.fingerprint for item in values if item is not None}) == 1
    assert values[0].confidence is OptimizationConfidence.PROJECTED


def test_confidence_is_part_of_fingerprint() -> None:
    proposal = FakeOptimizationPort().get_snapshot("demo")
    assert proposal is not None
    with pytest.raises(ValidationError):
        OptimizationProposal.model_validate(
            {
                **proposal.model_dump(mode="python"),
                "confidence": OptimizationConfidence.VERIFIED,
            }
        )
