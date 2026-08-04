from __future__ import annotations

import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import (
    canonical_fingerprint,
    confidence,
    fingerprint,
    safe_text,
    tuple_only,
)


class ModelContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class ModelTaskType(StrEnum):
    GENERATION = "GENERATION"
    ANALYSIS = "ANALYSIS"
    PLANNING = "PLANNING"


class ModelArtifactType(StrEnum):
    FIRMWARE = "FIRMWARE"
    HARDWARE = "HARDWARE"
    INTERFACE = "INTERFACE"
    BOM = "BOM"


class ModelRequest(ModelContract):
    task_type: ModelTaskType
    artifact_type: ModelArtifactType
    context_projection: tuple[str, ...] = Field(max_length=128)
    engineering_constraints: tuple[str, ...] = Field(max_length=128)
    fingerprint: str

    @field_validator("context_projection", "engineering_constraints", mode="before")
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        tuple_only(value, field=info.field_name)
        return tuple(
            safe_text(item, field=info.field_name, maximum=512) for item in value
        )

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_request_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "ModelRequest":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("model request fingerprint mismatch")
        return self

    @classmethod
    def create(
        cls,
        *,
        task_type: ModelTaskType,
        artifact_type: ModelArtifactType,
        context_projection: tuple[str, ...],
        engineering_constraints: tuple[str, ...],
    ) -> "ModelRequest":
        provisional = cls.model_construct(
            task_type=task_type,
            artifact_type=artifact_type,
            context_projection=context_projection,
            engineering_constraints=engineering_constraints,
            fingerprint="sha256:" + "0" * 64,
        )
        return cls.model_validate(
            {
                **provisional.model_dump(mode="python"),
                "fingerprint": canonical_fingerprint(
                    provisional, exclude={"fingerprint"}
                ),
            }
        )


class ModelResponse(ModelContract):
    artifact_projection: tuple[str, ...] = Field(max_length=128)
    summary: str
    confidence: float
    fingerprint: str

    @field_validator("artifact_projection", mode="before")
    @classmethod
    def validate_projection(cls, value: object) -> object:
        tuple_only(value, field="artifact_projection")
        return tuple(safe_text(item, field="artifact_projection") for item in value)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="summary", maximum=1024)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        return confidence(value)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_response_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "ModelResponse":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("model response fingerprint mismatch")
        return self

    @classmethod
    def create(
        cls,
        *,
        artifact_projection: tuple[str, ...],
        summary: str,
        confidence: float,
    ) -> "ModelResponse":
        provisional = cls.model_construct(
            artifact_projection=artifact_projection,
            summary=summary,
            confidence=confidence,
            fingerprint="sha256:" + "0" * 64,
        )
        return cls.model_validate(
            {
                **provisional.model_dump(mode="python"),
                "fingerprint": canonical_fingerprint(
                    provisional, exclude={"fingerprint"}
                ),
            }
        )


@runtime_checkable
class ModelRuntimePort(Protocol):
    def generate(self, request: ModelRequest) -> ModelResponse: ...


def validate_model_request(value: object) -> ModelRequest:
    if type(value) is not ModelRequest:
        raise TypeError("model request is invalid")
    return ModelRequest.model_validate(copy.deepcopy(value.model_dump(mode="python")))


def validate_model_response(value: object) -> ModelResponse:
    if type(value) is not ModelResponse:
        raise TypeError("model response is invalid")
    return ModelResponse.model_validate(copy.deepcopy(value.model_dump(mode="python")))


def model_request_fingerprint(value: ModelRequest) -> str:
    return canonical_fingerprint(value, exclude={"fingerprint"})


def model_response_fingerprint(value: ModelResponse) -> str:
    return canonical_fingerprint(value, exclude={"fingerprint"})


__all__ = [
    "ModelArtifactType",
    "ModelContract",
    "ModelRequest",
    "ModelResponse",
    "ModelRuntimePort",
    "ModelTaskType",
    "model_request_fingerprint",
    "model_response_fingerprint",
    "validate_model_request",
    "validate_model_response",
]
