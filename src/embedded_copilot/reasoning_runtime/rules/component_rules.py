from __future__ import annotations

from embedded_copilot.reasoning_runtime.contracts import RuleResult
from embedded_copilot.reasoning_runtime.rules.context import RuleContext


def missing_component_candidate(context: RuleContext) -> RuleResult:
    references = tuple(
        item.file_id
        for item in context.datasheet_candidates
        if item.component_candidate is None
    )
    return RuleResult(
        rule_id="missing_component_candidate",
        rule_source="component",
        triggered=bool(references),
        references=references,
        reason=(
            "At least one datasheet source has no component candidate."
            if references
            else "Every datasheet source has a component candidate or none is present."
        ),
    )


def multiple_component_candidates(context: RuleContext) -> RuleResult:
    candidates = tuple(
        (item.file_id, item.component_candidate)
        for item in context.datasheet_candidates
        if item.component_candidate is not None
    )
    labels = {
        (candidate.family, candidate.model)
        for _, candidate in candidates
        if candidate is not None
    }
    references = tuple(item[0] for item in candidates) if len(labels) > 1 else ()
    return RuleResult(
        rule_id="multiple_component_candidates",
        rule_source="component",
        triggered=bool(references),
        references=references,
        reason=(
            "Multiple distinct component candidates require role confirmation."
            if references
            else "Distinct component candidate ambiguity was not detected."
        ),
    )
