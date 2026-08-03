from __future__ import annotations

from pydantic import ConfigDict, field_validator

from embedded_copilot.reasoning import ReasoningMode, ReasoningResponse
from embedded_copilot.reasoning.models import normalize_text, identifier
from embedded_copilot.schemas.result import ContractModel


class ReasoningWebContract(ContractModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class ReasoningQueryRequest(ReasoningWebContract):
    recommendation_id: str
    mode: ReasoningMode
    question: str

    @field_validator("mode", mode="before")
    @classmethod
    def validate_mode(cls, value: object) -> ReasoningMode:
        if isinstance(value, ReasoningMode):
            return value
        if isinstance(value, str):
            try:
                return ReasoningMode(value)
            except ValueError as error:
                raise ValueError("mode is invalid") from error
        raise ValueError("mode is invalid")

    @field_validator("recommendation_id", mode="before")
    @classmethod
    def validate_recommendation_id(cls, value: object) -> str:
        return identifier(value, field="recommendation_id")

    @field_validator("question", mode="before")
    @classmethod
    def validate_question(cls, value: object) -> str:
        return normalize_text(value, field="question", maximum=512)


class ReasoningQueryResponse(ReasoningWebContract):
    summary: str
    explanation: str
    tradeoffs: tuple[str, ...]
    risks: tuple[str, ...]
    references: tuple[str, ...]
    confidence: float

    @classmethod
    def from_response(cls, response: ReasoningResponse) -> "ReasoningQueryResponse":
        return cls(
            summary=response.summary,
            explanation=response.explanation,
            tradeoffs=response.tradeoffs,
            risks=response.risks,
            references=response.references,
            confidence=response.confidence,
        )


__all__ = ["ReasoningQueryRequest", "ReasoningQueryResponse"]
