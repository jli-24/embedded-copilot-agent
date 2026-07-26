from __future__ import annotations

from embedded_copilot.reasoning_runtime.contracts import RuleResult
from embedded_copilot.reasoning_runtime.rules.context import RuleContext


def missing_context(context: RuleContext) -> RuleResult:
    triggered = not context.reference_ids
    return RuleResult(
        rule_id="missing_context",
        rule_source="context",
        triggered=triggered,
        references=(),
        reason=(
            "No safe engineering context is available for deterministic review."
            if triggered
            else "At least one safe engineering context reference is available."
        ),
    )
