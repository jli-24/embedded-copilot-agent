from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from embedded_copilot.reasoning_runtime import (
    CapabilityEntry,
    NextStep,
    ReasoningContextSnapshot,
    ReasoningRequest,
    ReasoningTrace,
    RuleResult,
    build_reasoning_context_snapshot,
    create_reasoning_runtime,
)
from embedded_copilot.context_runtime.contracts import (
    EngineeringContextRequest,
    EngineeringContextResponse,
    EngineeringContextSummary,
)

CONTEXT_ID = "context:0123456789abcdef01234567"


def _snapshot() -> ReasoningContextSnapshot:
    request = EngineeringContextRequest(
        session_id="session:1",
        task_intent="Review the supplied engineering context.",
        reference_ids=(),
    )
    response = EngineeringContextResponse(
        context_summary=EngineeringContextSummary(
            context_id=CONTEXT_ID,
            task_intent=request.task_intent,
        )
    )
    return build_reasoning_context_snapshot(
        request,
        response,
        expected_context_id=CONTEXT_ID,
    )


def test_foundation_contracts_are_frozen_and_forbid_extra_fields() -> None:
    snapshot = _snapshot()

    with pytest.raises(ValidationError, match="frozen"):
        snapshot.task_intent = "Changed"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="extra"):
        ReasoningContextSnapshot.model_validate(
            {**snapshot.model_dump(mode="python"), "path": "private.pdf"}
        )


def test_snapshot_requires_versioned_aligned_safe_sources() -> None:
    with pytest.raises(ValidationError):
        ReasoningContextSnapshot(
            schema_version="2.0",  # type: ignore[arg-type]
            snapshot_fingerprint=f"sha256:{'0' * 64}",
            context_id=CONTEXT_ID,
            task_intent="Review context.",
            reference_ids=(),
            source_types=(),
        )
    with pytest.raises(ValidationError):
        ReasoningContextSnapshot(
            snapshot_fingerprint="invalid",
            context_id=CONTEXT_ID,
            task_intent="Review context.",
            reference_ids=(),
            source_types=(),
        )


def test_rule_trace_records_version_source_and_request_trace() -> None:
    rule = RuleResult(
        rule_id="missing_context",
        rule_source="context",
        triggered=True,
        references=(),
        reason="No safe engineering context was supplied.",
    )
    trace = ReasoningTrace(
        trace_id="trace:1",
        context_id=_snapshot().context_id,
        snapshot_fingerprint=_snapshot().snapshot_fingerprint,
        capabilities_applied=(CapabilityEntry(name="context_analysis"),),
        rules_applied=(rule,),
        generated_sections=("summary", "risk"),
    )

    assert rule.rule_version == "1.0"
    assert rule.rule_source == "context"
    assert trace.rules_applied == (rule,)


def test_inactive_rule_cannot_carry_references() -> None:
    with pytest.raises(ValidationError):
        RuleResult(
            rule_id="interface_review_required",
            rule_source="interface",
            triggered=False,
            references=("file:1",),
            reason="No interface candidates were supplied.",
        )


@pytest.mark.parametrize(
    "action",
    (
        "Execute a shell command",
        "Apply patch",
        "Flash firmware",
        "Control VSCode",
    ),
)
def test_next_steps_reject_mutation_and_execution_actions(action: str) -> None:
    with pytest.raises(ValidationError):
        NextStep(action=action, reason="Engineer review is required.")


def test_foundation_runtime_returns_review_required_canonical_response() -> None:
    request = ReasoningRequest(
        session_id="session:1",
        trace_id="trace:1",
        context_snapshot=_snapshot(),
    )

    response = asyncio.run(create_reasoning_runtime().reasoning_port().analyze(request))

    assert response.output_type == "reasoning_suggestion"
    assert response.reasoning_summary.presentation_summary is None
    assert response.reasoning_summary.confidence == "low"
    assert response.trace.trace_id == "trace:1"
    assert response.review_required is True
