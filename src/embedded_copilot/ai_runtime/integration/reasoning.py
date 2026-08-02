"""Adapter from the existing public ReasoningPort to structured AI output."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from embedded_copilot.ai_runtime.models import (
    EngineeringModelOutput,
    EngineeringModelRequest,
    engineering_model_output_fingerprint,
)
from embedded_copilot.conversation.models import ReasoningOutput
from embedded_copilot.conversation.reasoning import ReasoningPort

_OUTPUT_INSTRUCTION = (
    "Return one JSON object with exactly requirement_analysis, "
    "architecture_recommendation, hardware_suggestion, risk_analysis, "
    "next_action, and reference_ids. reference_ids must be a JSON array."
)


class _RawEngineeringModelOutput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
        strict=True,
    )

    requirement_analysis: str
    architecture_recommendation: str
    hardware_suggestion: str
    risk_analysis: str
    next_action: str
    reference_ids: tuple[str, ...]

    @field_validator("reference_ids", mode="before")
    @classmethod
    def normalize_json_references(cls, value: object) -> object:
        if type(value) is list:
            return tuple(value)
        return value


class ReasoningEngineeringModelPort:
    __slots__ = ("_reasoning",)

    def __init__(self, reasoning: ReasoningPort) -> None:
        if not isinstance(reasoning, ReasoningPort):
            raise TypeError("reasoning_port is invalid")
        self._reasoning = reasoning

    async def generate(
        self,
        request: EngineeringModelRequest,
    ) -> EngineeringModelOutput:
        checked = EngineeringModelRequest.model_validate(request.model_copy(deep=True))
        output = await self._reasoning.reason(
            user_message_summary=checked.message,
            context_summaries=(*checked.context_summaries, _OUTPUT_INSTRUCTION),
            task_intent="DESIGN_REVIEW",
        )
        if type(output) is not ReasoningOutput:
            raise ValueError("reasoning output is invalid")
        checked_output = ReasoningOutput.model_validate(output.model_copy(deep=True))
        raw = _RawEngineeringModelOutput.model_validate_json(
            checked_output.response.text
        )
        values = {
            name: getattr(raw, name) for name in type(raw).model_fields
        }
        return EngineeringModelOutput(
            **values,
            fingerprint=engineering_model_output_fingerprint(**values),
        )

