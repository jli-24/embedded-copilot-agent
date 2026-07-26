from __future__ import annotations

from embedded_copilot.reasoning_runtime.contracts import RuleResult
from embedded_copilot.reasoning_runtime.rules.context import RuleContext


def visual_observation_review_required(context: RuleContext) -> RuleResult:
    references = tuple(item.reference_id for item in context.vision_refs)
    return RuleResult(
        rule_id="visual_observation_review_required",
        rule_source="vision",
        triggered=bool(references),
        references=references,
        reason=(
            "Vision references contain no engineer-validated visual observations."
            if references
            else "No vision references require visual observation review."
        ),
    )
