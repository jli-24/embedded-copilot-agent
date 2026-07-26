from __future__ import annotations

import copy
import math
import re
from collections.abc import Iterator, Mapping
from enum import StrEnum
from typing import Literal, TypeAlias

from pydantic import (
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from embedded_copilot.intelligence._validation import (
    safe_identifier,
    safe_text,
    safe_text_tuple,
)
from embedded_copilot.schemas.result import ContractModel

ModelMetadataScalar: TypeAlias = str | int | float | bool | None
_ALLOWED_METADATA_KEYS = frozenset({"cached", "finish_reason", "latency_ms"})


class IntelligenceContractModel(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class ModelCapability(StrEnum):
    CHAT = "CHAT"
    VISION = "VISION"
    CODE = "CODE"
    REASONING = "REASONING"


class _FrozenMetadata(Mapping[str, ModelMetadataScalar]):
    __slots__ = ("_items",)

    def __init__(self, items: Iterator[tuple[str, ModelMetadataScalar]]) -> None:
        self._items = tuple(items)

    def __getitem__(self, key: str) -> ModelMetadataScalar:
        for candidate, value in self._items:
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __deepcopy__(self, memo: dict[int, object]) -> "_FrozenMetadata":
        return self


def _validated_metadata(value: object) -> dict[str, ModelMetadataScalar]:
    copied = copy.deepcopy(value)
    if not isinstance(copied, Mapping):
        raise ValueError("model metadata must be a mapping")
    validated: dict[str, ModelMetadataScalar] = {}
    for raw_key, raw_value in copied.items():
        if not isinstance(raw_key, str):
            raise ValueError("model metadata key is invalid")
        key = raw_key.strip().casefold()
        if key not in _ALLOWED_METADATA_KEYS:
            raise ValueError("model metadata key is forbidden")
        item: ModelMetadataScalar
        if key == "cached":
            if not isinstance(raw_value, bool):
                raise ValueError("model metadata value is invalid")
            item = raw_value
        elif key == "finish_reason":
            item = safe_text(raw_value, field="model metadata", max_length=64)
        elif (
            isinstance(raw_value, bool)
            or not isinstance(raw_value, (int, float))
            or not math.isfinite(raw_value)
            or raw_value < 0
        ):
            raise ValueError("model metadata number is invalid")
        else:
            item = raw_value
        validated[key] = item
    return dict(sorted(validated.items()))


class ModelInput(IntelligenceContractModel):
    message_summary: str
    context_summaries: tuple[str, ...] = ()

    @field_validator("message_summary", mode="before")
    @classmethod
    def validate_message_summary(cls, value: object) -> str:
        return safe_text(value, field="message_summary", max_length=512)

    @field_validator("context_summaries", mode="before")
    @classmethod
    def validate_context_summaries(cls, value: object) -> object:
        return safe_text_tuple(
            value,
            field="context_summary",
            max_length=512,
        )


class ModelUsage(IntelligenceContractModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_total(self) -> "ModelUsage":
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("model usage total is inconsistent")
        return self


class ModelResponse(IntelligenceContractModel):
    output_type: Literal["reasoning_suggestion"] = "reasoning_suggestion"
    text: str
    metadata: Mapping[str, ModelMetadataScalar] = Field(
        default_factory=lambda: _FrozenMetadata(iter(()))
    )
    usage: ModelUsage | None = None
    source: str

    @field_validator("text", mode="before")
    @classmethod
    def validate_text(cls, value: object) -> str:
        return safe_text(value, field="text", max_length=4096)

    @field_validator("source", mode="before")
    @classmethod
    def validate_source(cls, value: object) -> str:
        return safe_identifier(value, field="source")

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, value: object) -> object:
        return _validated_metadata(value)

    @field_validator("metadata", mode="after")
    @classmethod
    def freeze_metadata(
        cls,
        value: Mapping[str, ModelMetadataScalar],
    ) -> Mapping[str, ModelMetadataScalar]:
        return _FrozenMetadata(iter(value.items()))

    @field_validator("usage", mode="before")
    @classmethod
    def isolate_usage(cls, value: object) -> object:
        return copy.deepcopy(value)

    @field_serializer("metadata")
    def serialize_metadata(
        self,
        value: Mapping[str, ModelMetadataScalar],
    ) -> dict[str, ModelMetadataScalar]:
        return dict(value)
