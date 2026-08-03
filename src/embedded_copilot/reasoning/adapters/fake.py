from __future__ import annotations

from embedded_copilot.reasoning.contracts import (
    ReasoningMode,
    ReasoningRequest,
    ReasoningResponse,
)
from embedded_copilot.reasoning.models import canonical_fingerprint


class FakeReasoningPort:
    def reason(self, request: ReasoningRequest) -> ReasoningResponse:
        recommendation = request.recommendation
        mode = request.reasoning_mode
        summary = f"Reviewable {mode.value.lower()} of recommendation {recommendation.recommendation_id}."
        explanation = (
            f"This explanation is derived from the supplied recommendation: "
            f"{recommendation.summary}"
        )
        tradeoffs = (
            ("The recommendation remains subject to engineering review.",)
            if mode in {ReasoningMode.COMPARE, ReasoningMode.GENERATE_PLAN}
            else ()
        )
        risks = tuple(recommendation.risks[:8])
        material = ReasoningResponse.model_construct(
            summary=summary,
            explanation=explanation,
            tradeoffs=tradeoffs,
            risks=risks,
            references=tuple(
                reference.reference_id for reference in request.evidence_references
            ),
            confidence=0.5,
            fingerprint="sha256:" + "0" * 64,
        )
        return ReasoningResponse.model_validate(
            {
                **material.model_dump(mode="python"),
                "fingerprint": canonical_fingerprint(material, exclude={"fingerprint"}),
            }
        )


__all__ = ["FakeReasoningPort"]
