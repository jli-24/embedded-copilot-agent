from __future__ import annotations

import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import (
    canonical_fingerprint,
    confidence,
    fingerprint,
    identifier,
    safe_text,
    tuple_only,
)


class MultimodalContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class InputType(StrEnum):
    PCB = "PCB"
    SCHEMATIC = "SCHEMATIC"
    DATASHEET = "DATASHEET"
    DOCUMENT = "DOCUMENT"
    IMAGE = "IMAGE"


class VisionRequest(MultimodalContract):
    project_id: str
    source_reference: str
    input_type: InputType
    context_fingerprint: str
    fingerprint: str

    @field_validator("project_id", "source_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("context_fingerprint", "fingerprint", mode="before")
    @classmethod
    def validate_fingerprints(cls, value: object, info) -> str:
        return fingerprint(value, field=info.field_name)

    @model_validator(mode="after")
    def verify(self) -> VisionRequest:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("vision request fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> VisionRequest:
        normalized = dict(values)
        for field in ("project_id", "source_reference"):
            if field in normalized:
                normalized[field] = identifier(normalized[field], field=field)
        if "context_fingerprint" in normalized:
            normalized["context_fingerprint"] = fingerprint(
                normalized["context_fingerprint"], field="context_fingerprint"
            )
        provisional = cls.model_construct(
            **{**normalized, "fingerprint": "sha256:" + "0" * 64}
        )
        normalized["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(normalized)


class VisionObservation(MultimodalContract):
    observation_id: str
    project_id: str
    source_reference: str
    observation_type: InputType
    content: tuple[str, ...] = Field(max_length=128)
    confidence: float
    fingerprint: str

    @field_validator("observation_id", "project_id", "source_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("content", mode="before")
    @classmethod
    def validate_content_tuple(cls, value: object) -> object:
        return tuple_only(value, field="content")

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(safe_text(item, field="content_item") for item in value)
        if len(checked) != len(set(checked)):
            raise ValueError("observation content must be unique")
        return checked

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        return confidence(value)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> VisionObservation:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("vision observation fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> VisionObservation:
        normalized = dict(values)
        for field in ("observation_id", "project_id", "source_reference"):
            if field in normalized:
                normalized[field] = identifier(normalized[field], field=field)
        if "content" in normalized:
            normalized["content"] = tuple(
                safe_text(item, field="content_item")
                for item in tuple_only(normalized["content"], field="content")
            )
        provisional = cls.model_construct(
            **{**normalized, "fingerprint": "sha256:" + "0" * 64}
        )
        normalized["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(normalized)


class EngineeringInterpretation(MultimodalContract):
    interpretation_id: str
    observation_reference: str
    summary: str
    risk: str
    confidence: float
    fingerprint: str

    @field_validator("interpretation_id", "observation_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("summary", "risk", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        return confidence(value)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> EngineeringInterpretation:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("interpretation fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> EngineeringInterpretation:
        normalized = dict(values)
        for field in ("interpretation_id", "observation_reference"):
            if field in normalized:
                normalized[field] = identifier(normalized[field], field=field)
        for field in ("summary", "risk"):
            if field in normalized:
                normalized[field] = safe_text(normalized[field], field=field)
        provisional = cls.model_construct(
            **{**normalized, "fingerprint": "sha256:" + "0" * 64}
        )
        normalized["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(normalized)


class MultimodalAnalysisProjection(MultimodalContract):
    observation: VisionObservation
    interpretation: EngineeringInterpretation | None = None
    fingerprint: str

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> MultimodalAnalysisProjection:
        if (
            self.interpretation is not None
            and self.interpretation.observation_reference
            != self.observation.observation_id
        ):
            raise ValueError("interpretation observation binding mismatch")
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("multimodal projection fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> MultimodalAnalysisProjection:
        normalized = dict(values)
        if "observation" in normalized:
            normalized["observation"] = validate_observation(normalized["observation"])
        if normalized.get("interpretation") is not None:
            normalized["interpretation"] = validate_interpretation(
                normalized["interpretation"]
            )
        provisional = cls.model_construct(
            **{**normalized, "fingerprint": "sha256:" + "0" * 64}
        )
        normalized["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(normalized)


@runtime_checkable
class VisionModelPort(Protocol):
    def analyze(self, request: VisionRequest) -> VisionObservation: ...


@runtime_checkable
class EngineeringReasoningPort(Protocol):
    def analyze_observation(
        self, observation: VisionObservation
    ) -> EngineeringInterpretation: ...


def validate_request(value: object) -> VisionRequest:
    if type(value) is not VisionRequest:
        raise TypeError("vision request is invalid")
    return VisionRequest.model_validate(copy.deepcopy(value.model_dump(mode="python")))


def validate_observation(value: object) -> VisionObservation:
    if type(value) is not VisionObservation:
        raise TypeError("vision observation is invalid")
    return VisionObservation.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


def validate_interpretation(value: object) -> EngineeringInterpretation:
    if type(value) is not EngineeringInterpretation:
        raise TypeError("engineering interpretation is invalid")
    return EngineeringInterpretation.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


def validate_projection(value: object) -> MultimodalAnalysisProjection:
    if type(value) is not MultimodalAnalysisProjection:
        raise TypeError("multimodal projection is invalid")
    return MultimodalAnalysisProjection.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


__all__ = [
    "EngineeringInterpretation",
    "EngineeringReasoningPort",
    "InputType",
    "MultimodalAnalysisProjection",
    "MultimodalContract",
    "VisionModelPort",
    "VisionObservation",
    "VisionRequest",
    "validate_interpretation",
    "validate_observation",
    "validate_projection",
    "validate_request",
]
