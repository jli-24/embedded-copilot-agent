from __future__ import annotations

import copy
import math
from collections.abc import Iterator, Mapping
from typing import BinaryIO, Protocol, TypeAlias

from pydantic import Field, field_serializer, field_validator

from embedded_copilot.intelligence._validation import safe_identifier, safe_text
from embedded_copilot.intelligence.models import IntelligenceContractModel
from embedded_copilot.multimodal.context import AttachmentBinding

FileMetadataScalar: TypeAlias = str | int | float | bool | None
_ALLOWED_METADATA = frozenset({"format", "height", "page_count", "width"})


class _FrozenFileMetadata(Mapping[str, FileMetadataScalar]):
    __slots__ = ("_items",)

    def __init__(self, items: Iterator[tuple[str, FileMetadataScalar]]) -> None:
        self._items = tuple(items)

    def __getitem__(self, key: str) -> FileMetadataScalar:
        for candidate, value in self._items:
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __deepcopy__(self, memo: dict[int, object]) -> "_FrozenFileMetadata":
        return self


class TemporaryFileSummary(IntelligenceContractModel):
    reference_id: str
    summary: str
    metadata: Mapping[str, FileMetadataScalar] = Field(
        default_factory=lambda: _FrozenFileMetadata(iter(()))
    )

    @field_validator("reference_id", mode="before")
    @classmethod
    def validate_reference_id(cls, value: object) -> str:
        return safe_identifier(value, field="reference_id")

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="summary", max_length=512)

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, value: object) -> object:
        copied = copy.deepcopy(value)
        if not isinstance(copied, Mapping):
            raise ValueError("file summary metadata must be a mapping")
        result: dict[str, FileMetadataScalar] = {}
        for raw_key, raw_value in copied.items():
            if not isinstance(raw_key, str):
                raise ValueError("file summary metadata key is invalid")
            key = raw_key.strip().casefold()
            if key not in _ALLOWED_METADATA:
                raise ValueError("file summary metadata key is forbidden")
            if raw_value is not None and not isinstance(
                raw_value,
                (str, int, float, bool),
            ):
                raise ValueError("file summary metadata value is invalid")
            if isinstance(raw_value, str):
                item: FileMetadataScalar = safe_text(
                    raw_value,
                    field="file summary metadata",
                    max_length=64,
                )
            elif isinstance(raw_value, float) and not math.isfinite(raw_value):
                raise ValueError("file summary metadata number is invalid")
            else:
                item = raw_value
            result[key] = item
        return dict(sorted(result.items()))

    @field_validator("metadata", mode="after")
    @classmethod
    def freeze_metadata(
        cls,
        value: Mapping[str, FileMetadataScalar],
    ) -> Mapping[str, FileMetadataScalar]:
        return _FrozenFileMetadata(iter(value.items()))

    @field_serializer("metadata")
    def serialize_metadata(
        self,
        value: Mapping[str, FileMetadataScalar],
    ) -> dict[str, FileMetadataScalar]:
        return dict(value)


class FileExtractor(Protocol):
    def extract(
        self,
        stream: BinaryIO,
        *,
        binding: AttachmentBinding,
    ) -> TemporaryFileSummary: ...
