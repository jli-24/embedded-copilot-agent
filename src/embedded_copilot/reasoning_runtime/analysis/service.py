from __future__ import annotations

import copy

from embedded_copilot.reasoning_runtime.analysis.analyzer import analyze_context
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
        sections = ("summary", "risk") if risks else ("summary",)
        return ReasoningResponse(
            reasoning_summary=analyze_context(snapshot),
            risks=risks,
            trace=ReasoningTrace(
                trace_id=isolated.trace_id,
                context_id=snapshot.context_id,
                snapshot_fingerprint=snapshot.snapshot_fingerprint,
                rules_applied=rules,
                generated_sections=sections,
            ),
        )
