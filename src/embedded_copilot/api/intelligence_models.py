from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from embedded_copilot.engineering_intelligence.contracts import (
    EngineeringContextSnapshot,
    EngineeringIntelligenceResponse,
)


class IntelligenceWebContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class IntelligenceQueryRequest(IntelligenceWebContract):
    project_id: str
    question: str

    @field_validator("project_id", "question", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{info.field_name} is invalid")
        text = value.strip()
        if not text or len(text) > (160 if info.field_name == "project_id" else 512):
            raise ValueError(f"{info.field_name} is invalid")
        if any(char in text for char in ("\x00", "\r", "\n")):
            raise ValueError(f"{info.field_name} is invalid")
        return text


class IntelligenceContextResponse(IntelligenceWebContract):
    context: EngineeringContextSnapshot


class IntelligenceQueryResponse(IntelligenceWebContract):
    result: EngineeringIntelligenceResponse
