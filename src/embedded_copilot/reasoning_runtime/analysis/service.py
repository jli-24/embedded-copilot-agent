from __future__ import annotations

import copy

from embedded_copilot.reasoning_runtime.analysis.analyzer import analyze_context
from embedded_copilot.reasoning_runtime.capabilities import active_capabilities
from embedded_copilot.reasoning_runtime.contracts import (
    ReasoningRequest,
    ReasoningResponse,
    ReasoningTrace,
)
from embedded_copilot.reasoning_runtime.rules import (
    RuleContext,
    evaluate_rules,
    project_risks,
)
from embedded_copilot.reasoning_runtime.planning import plan_next_steps


class CanonicalReasoningPort:
    async def analyze(self, request: ReasoningRequest) -> ReasoningResponse:
        isolated = ReasoningRequest.model_validate(
            copy.deepcopy(request.model_dump(mode="python"))
        )
        snapshot = isolated.context_snapshot
        context = RuleContext(
            reference_ids=snapshot.reference_ids,
            source_types=snapshot.source_types,
            datasheet_candidates=snapshot.datasheet_candidates,
            file_summaries=snapshot.file_summaries,
            vision_refs=snapshot.vision_refs,
        )
        rules = evaluate_rules(context)
        risks = project_risks(context, rules)
        next_steps = plan_next_steps(rules)
        sections = (
            ("summary", "risk", "next_step") if risks else ("summary", "next_step")
        )
        return ReasoningResponse(
            reasoning_summary=analyze_context(snapshot),
            risks=risks,
            next_steps=next_steps,
            trace=ReasoningTrace(
                trace_id=isolated.trace_id,
                context_id=snapshot.context_id,
                snapshot_fingerprint=snapshot.snapshot_fingerprint,
                capabilities_applied=active_capabilities(),
                rules_applied=rules,
                generated_sections=sections,
            ),
        )
