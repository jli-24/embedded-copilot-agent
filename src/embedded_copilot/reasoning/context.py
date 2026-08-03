from __future__ import annotations

import copy
from typing import Protocol

from pydantic import BaseModel, ConfigDict, model_validator

from embedded_copilot.engineering_intelligence import (
    EngineeringContextSnapshot,
    EngineeringRecommendation,
)

from .contracts import ReasoningEvidenceReference


class ReasoningInputProjection(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )

    context_snapshot: EngineeringContextSnapshot
    recommendation: EngineeringRecommendation
    evidence_references: tuple[ReasoningEvidenceReference, ...]

    @model_validator(mode="before")
    @classmethod
    def require_tuple_and_copy(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        if not isinstance(value.get("evidence_references"), tuple):
            raise ValueError("evidence_references must be a tuple")
        return copy.deepcopy(value)

    @model_validator(mode="after")
    def validate_projection(self) -> "ReasoningInputProjection":
        references = tuple(item.reference_id for item in self.evidence_references)
        if len(references) != len(set(references)):
            raise ValueError("evidence references must be unique")
        if set(references) != set(self.recommendation.evidence_refs):
            raise ValueError("evidence references do not match recommendation")
        return self


class ReasoningInputResolver(Protocol):
    def resolve(self, recommendation_id: str) -> ReasoningInputProjection | None: ...


def validate_reasoning_input(
    value: ReasoningInputProjection,
) -> ReasoningInputProjection:
    if type(value) is not ReasoningInputProjection:
        raise TypeError("reasoning input must be a typed projection")
    return ReasoningInputProjection.model_validate(copy.deepcopy(value))


__all__ = [
    "ReasoningInputProjection",
    "ReasoningInputResolver",
    "validate_reasoning_input",
]
