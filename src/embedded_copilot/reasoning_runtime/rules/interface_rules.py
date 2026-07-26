from __future__ import annotations

from embedded_copilot.reasoning_runtime.contracts import RuleResult
from embedded_copilot.reasoning_runtime.rules.context import RuleContext


def interface_review_required(context: RuleContext) -> RuleResult:
    references = tuple(
        item.file_id for item in context.datasheet_candidates if item.interfaces
    )
    return RuleResult(
        rule_id="interface_review_required",
        rule_source="interface",
        triggered=bool(references),
        references=references,
        reason=(
            "Interface candidates require engineer compatibility verification."
            if references
            else "No interface candidates are available for compatibility review."
        ),
    )
