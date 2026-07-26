from __future__ import annotations

import copy

from embedded_copilot.reasoning_runtime.contracts import (
    ReasoningPort,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningSummary,
    ReasoningTrace,
)
from embedded_copilot.reasoning_runtime.facade import ReasoningRuntime


class _FoundationReasoningPort:
    async def analyze(self, request: ReasoningRequest) -> ReasoningResponse:
        isolated = ReasoningRequest.model_validate(
            copy.deepcopy(request.model_dump(mode="python"))
        )
        snapshot = isolated.context_snapshot
        return ReasoningResponse(
            reasoning_summary=ReasoningSummary(
                summary="Engineering context is available for engineer review.",
                confidence="low",
                assumptions=(
                    "The supplied context remains subject to engineer validation.",
                ),
            ),
            trace=ReasoningTrace(
                trace_id=isolated.trace_id,
                context_id=snapshot.context_id,
                snapshot_fingerprint=snapshot.snapshot_fingerprint,
                generated_sections=("summary",),
            ),
        )


def create_reasoning_runtime() -> ReasoningRuntime:
    port: ReasoningPort = _FoundationReasoningPort()
    return ReasoningRuntime._compose(port)
