from __future__ import annotations

import math
from collections.abc import Iterator, Mapping
from enum import StrEnum
from typing import Protocol, TypeAlias

from pydantic import Field, field_serializer, field_validator

from embedded_copilot.intelligence._validation import safe_text
from embedded_copilot.intelligence.models import IntelligenceContractModel
from embedded_copilot.vision_runtime.contracts import VisionRequest

VisionMetadataValue: TypeAlias = str | float | bool
_ALLOWED_METADATA = frozenset({"cached", "finish_reason", "latency_ms"})


class VisionProviderUnavailable(RuntimeError):
    """A safe provider-unavailable failure for the API boundary."""


class VisionProviderTimeout(TimeoutError):
    """A safe request-scoped provider timeout."""


class VisionCapability(StrEnum):
    VISION = "VISION"


class _FrozenMetadata(Mapping[str, VisionMetadataValue]):
    __slots__ = ("_items",)

    def __init__(self, items: Iterator[tuple[str, VisionMetadataValue]]) -> None:
        self._items = tuple(items)

    def __getitem__(self, key: str) -> VisionMetadataValue:
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


class ProviderVisionResponse(IntelligenceContractModel):
    summary: str
    metadata: Mapping[str, VisionMetadataValue] = Field(
        default_factory=lambda: _FrozenMetadata(iter(()))
    )

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="summary", max_length=4096)

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            raise ValueError("vision metadata must be a mapping")
        validated: dict[str, VisionMetadataValue] = {}
        for raw_key, raw_value in value.items():
            if not isinstance(raw_key, str):
                raise ValueError("vision metadata key is invalid")
            key = raw_key.strip().casefold()
            if key not in _ALLOWED_METADATA:
                raise ValueError("vision metadata key is forbidden")
            if key == "cached":
                if not isinstance(raw_value, bool):
                    raise ValueError("vision metadata value is invalid")
                validated[key] = raw_value
            elif key == "finish_reason":
                validated[key] = safe_text(
                    raw_value,
                    field="finish_reason",
                    max_length=64,
                )
            elif (
                isinstance(raw_value, bool)
                or not isinstance(raw_value, (int, float))
                or not math.isfinite(raw_value)
                or raw_value < 0
            ):
                raise ValueError("vision metadata value is invalid")
            else:
                validated[key] = float(raw_value)
        return validated

    @field_validator("metadata", mode="after")
    @classmethod
    def freeze_metadata(
        cls,
        value: Mapping[str, VisionMetadataValue],
    ) -> Mapping[str, VisionMetadataValue]:
        return _FrozenMetadata(iter(sorted(value.items())))

    @field_serializer("metadata")
    def serialize_metadata(
        self,
        value: Mapping[str, VisionMetadataValue],
    ) -> dict[str, VisionMetadataValue]:
        return dict(value)


class VisionProvider(Protocol):
    provider_id: str
    supported_capabilities: tuple[VisionCapability, ...]

    async def analyze(
        self,
        request: VisionRequest,
        *,
        reference_summary: str,
    ) -> ProviderVisionResponse: ...
