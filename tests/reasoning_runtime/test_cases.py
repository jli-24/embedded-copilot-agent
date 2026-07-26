from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from embedded_copilot.reasoning_runtime import (
    ReasoningContextSnapshot,
    ReasoningRequest,
    create_reasoning_runtime,
)

CASES = Path(__file__).parents[1] / "reasoning_cases"


@pytest.mark.parametrize(
    "path",
    tuple(sorted(CASES.glob("*.json"))),
    ids=lambda path: path.stem,
)
def test_reasoning_case_preserves_canonical_semantics(path: Path) -> None:
    case = json.loads(path.read_text(encoding="utf-8"))
    snapshot = ReasoningContextSnapshot.model_validate(case["input"])

    response = asyncio.run(
        create_reasoning_runtime()
        .reasoning_port()
        .analyze(
            ReasoningRequest(
                session_id="session:evaluation",
                trace_id="trace:evaluation",
                context_snapshot=snapshot,
            )
        )
    )
    expected = case["expected"]

    assert response.reasoning_summary.confidence == expected["confidence"]
    assert response.reasoning_summary.presentation_summary is None
    assert tuple(item.category for item in response.risks) == tuple(expected["risks"])
    assert tuple(
        item.rule_id for item in response.trace.rules_applied if item.triggered
    ) == tuple(expected["triggered_rules"])
    assert all(item.rule_version == "1.0" for item in response.trace.rules_applied)
    assert tuple(item.action for item in response.next_steps) == tuple(
        expected["next_steps"]
    )
    assert response.trace.snapshot_fingerprint == snapshot.snapshot_fingerprint
