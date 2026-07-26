from __future__ import annotations

import copy

from embedded_copilot.reasoning_runtime.analysis.analyzer import analyze_context
from embedded_copilot.reasoning_runtime.contracts import (
    ReasoningRequest,
    ReasoningResponse,
    ReasoningTrace,
)


class CanonicalReasoningPort:
    async def analyze(self, request: ReasoningRequest) -> ReasoningResponse:
        isolated = ReasoningRequest.model_validate(
            copy.deepcopy(request.model_dump(mode="python"))
        )
        snapshot = isolated.context_snapshot
        return ReasoningResponse(
            reasoning_summary=analyze_context(snapshot),
            trace=ReasoningTrace(
                trace_id=isolated.trace_id,
                context_id=snapshot.context_id,
                snapshot_fingerprint=snapshot.snapshot_fingerprint,
                generated_sections=("summary",),
            ),
        )
