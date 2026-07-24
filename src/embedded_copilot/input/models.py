from __future__ import annotations

import copy
import math
import re
from collections.abc import Iterator, Mapping
from enum import StrEnum
from typing import TypeAlias

from pydantic import (
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from embedded_copilot.schemas.result import ContractModel


SafeMetadataScalar: TypeAlias = str | int | float | bool | None
_ATTACHMENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ABSOLUTE_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/|file://)", re.IGNORECASE)
_SENSITIVE_KEY_PARTS = (
    "body",
    "content",
    "credential",
    "home",
    "password",
    "path",
    "secret",
    "temp",
    "token",
    "user",
)


def _contains_sensitive_key(value: str) -> bool:
    tokens = re.findall(r"[a-z0-9]+", value.casefold())
    return any(token in _SENSITIVE_KEY_PARTS for token in tokens)


class _FrozenMetadata(Mapping[str, SafeMetadataScalar]):
    __slots__ = ("_items",)

    def __init__(self, items: Iterator[tuple[str, SafeMetadataScalar]]) -> None:
        self._items = tuple(items)

    def __getitem__(self, key: str) -> SafeMetadataScalar:
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


def _validated_metadata(
    value: object,
    *,
    allowed_keys: frozenset[str] | None = None,
) -> dict[str, SafeMetadataScalar]:
    try:
        return _validated_metadata_unchecked(value, allowed_keys=allowed_keys)
    except Exception:
        raise ValueError("input metadata is invalid") from None


def _validated_metadata_unchecked(
    value: object,
    *,
    allowed_keys: frozenset[str] | None,
) -> dict[str, SafeMetadataScalar]:
    copied = copy.deepcopy(value)
    if not isinstance(copied, Mapping):
        raise ValueError("input metadata must be a mapping")
    validated: dict[str, SafeMetadataScalar] = {}
    for raw_key, raw_value in copied.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise ValueError("input metadata keys must be non-empty strings")
        key = raw_key.strip()
        lowered = key.casefold()
        if allowed_keys is not None and lowered not in allowed_keys:
            raise ValueError("attachment metadata contains a forbidden key")
        if _contains_sensitive_key(lowered):
            raise ValueError("input metadata contains a forbidden key")
        if raw_value is not None and not isinstance(
            raw_value,
            (str, int, float, bool),
        ):
            raise ValueError("input metadata values must be scalar")
        value_item: SafeMetadataScalar = raw_value
        if isinstance(value_item, str):
            value_item = value_item.strip()
            if not value_item:
                raise ValueError("input metadata strings must not be blank")
            if _ABSOLUTE_PATH.match(value_item):
                raise ValueError("input metadata contains an absolute path")
        if isinstance(value_item, float) and not math.isfinite(value_item):
            raise ValueError("input metadata numbers must be finite")
        validated[key] = value_item
    return dict(sorted(validated.items(), key=lambda item: item[0]))


def _freeze_metadata(
    value: Mapping[str, SafeMetadataScalar],
) -> _FrozenMetadata:
    return _FrozenMetadata(iter(value.items()))


class AttachmentType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    SOURCE_CODE = "source_code"
    LOG = "log"
    DOCUMENT = "document"
    EDA = "eda"


class _InputContractModel(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )


class UserAttachment(_InputContractModel):
    id: str = Field(min_length=1, max_length=128)
    filename: str = Field(min_length=1)
    media_type: AttachmentType
    content_type: str = Field(min_length=1)
    size_bytes: int = Field(gt=0)
    metadata: Mapping[str, SafeMetadataScalar]

    @field_validator("id", mode="before")
    @classmethod
    def validate_id(cls, value: object) -> object:
        if isinstance(value, str):
            candidate = value.strip()
            if not _ATTACHMENT_ID.fullmatch(candidate):
                raise ValueError("attachment id is invalid")
            return candidate
        return value

    @field_validator("filename", mode="before")
    @classmethod
    def validate_filename(cls, value: object) -> object:
        if isinstance(value, str):
            candidate = value.strip()
            if (
                not candidate
                or candidate in {".", ".."}
                or "/" in candidate
                or "\\" in candidate
            ):
                raise ValueError("attachment filename is invalid")
            return candidate
        return value

    @field_validator("content_type", mode="before")
    @classmethod
    def normalize_content_type(cls, value: object) -> object:
        return value.strip().casefold() if isinstance(value, str) else value

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, value: object) -> object:
        return _validated_metadata(
            value,
            allowed_keys=frozenset({"category", "format"}),
        )

    @field_validator("metadata", mode="after")
    @classmethod
    def freeze_metadata(
        cls,
        value: Mapping[str, SafeMetadataScalar],
    ) -> Mapping[str, SafeMetadataScalar]:
        return _freeze_metadata(value)

    @field_serializer("metadata")
    def serialize_metadata(
        self,
        value: Mapping[str, SafeMetadataScalar],
    ) -> dict[str, SafeMetadataScalar]:
        return dict(value)

    @model_validator(mode="after")
    def validate_provenance(self) -> "UserAttachment":
        if set(self.metadata) != {"category", "format"}:
            raise ValueError("attachment metadata is incomplete")
        if self.metadata["category"] != self.media_type.value:
            raise ValueError("attachment metadata category does not match")
        return self


class UnifiedInputContext(_InputContractModel):
    text: str = ""
    attachments: tuple[UserAttachment, ...] = ()
    metadata: Mapping[str, SafeMetadataScalar] = Field(
        default_factory=lambda: _FrozenMetadata(iter(()))
    )

    @field_validator("text", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("attachments", mode="before")
    @classmethod
    def isolate_attachments(cls, value: object) -> object:
        return copy.deepcopy(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, value: object) -> object:
        return _validated_metadata(value)

    @field_validator("metadata", mode="after")
    @classmethod
    def freeze_metadata(
        cls,
        value: Mapping[str, SafeMetadataScalar],
    ) -> Mapping[str, SafeMetadataScalar]:
        return _freeze_metadata(value)

    @field_serializer("metadata")
    def serialize_metadata(
        self,
        value: Mapping[str, SafeMetadataScalar],
    ) -> dict[str, SafeMetadataScalar]:
        return dict(value)

    @model_validator(mode="after")
    def reject_duplicate_attachment_ids(self) -> "UnifiedInputContext":
        identifiers = [attachment.id.casefold() for attachment in self.attachments]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("duplicate attachment id")
        return self
