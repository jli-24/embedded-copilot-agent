from __future__ import annotations

import copy
import re
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from embedded_copilot.datasheet.models import UnifiedDatasheetModel
from embedded_copilot.firmware.review.models import FirmwareReviewResult
from embedded_copilot.input.models import AttachmentType
from embedded_copilot.schemas.result import ContractModel


_SAFE_SOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_SAFE_FILENAME = re.compile(r"^[^/\\\r\n\x00]{1,255}$")
_ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|file://|/(?:[^/\s]+/)+)", re.I)


class _EngineeringModel(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class EngineeringSourceReference(_EngineeringModel):
    attachment_id: str = Field(min_length=1, max_length=128)
    source_id: str = Field(min_length=1, max_length=160)
    filename: str = Field(min_length=1, max_length=255)

    @field_validator("attachment_id", "source_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object) -> object:
        if isinstance(value, str):
            candidate = value.strip()
            if not _SAFE_SOURCE_ID.fullmatch(candidate):
                raise ValueError("engineering source identifier is invalid")
            return candidate
        return value

    @field_validator("filename", mode="before")
    @classmethod
    def validate_filename(cls, value: object) -> object:
        if isinstance(value, str):
            candidate = value.strip()
            if not _SAFE_FILENAME.fullmatch(candidate) or candidate in {".", ".."}:
                raise ValueError("engineering source filename is invalid")
            return candidate
        return value


class ResolvedEngineeringSource(_EngineeringModel):
    reference: EngineeringSourceReference
    media_type: AttachmentType
    content_type: str = Field(min_length=1, max_length=128)
    data: bytes = Field(min_length=1)

    @field_validator("reference", mode="before")
    @classmethod
    def isolate_reference(cls, value: object) -> object:
        return copy.deepcopy(value)


class RealEngineeringError(_EngineeringModel):
    domain: Literal["datasheet", "firmware"]
    code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    message: str = Field(min_length=1, max_length=256)
    source_ids: tuple[str, ...] = ()

    @field_validator("message", mode="before")
    @classmethod
    def validate_message(cls, value: object) -> object:
        if isinstance(value, str):
            candidate = value.strip()
            if (
                not candidate
                or any(char in candidate for char in ("\r", "\n", "\x00"))
                or _ABSOLUTE_PATH.search(candidate)
            ):
                raise ValueError("engineering error message is unsafe")
            return candidate
        return value

    @field_validator("source_ids", mode="before")
    @classmethod
    def validate_source_ids(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)):
            return value
        normalized = tuple(item.strip() if isinstance(item, str) else item for item in value)
        if any(
            not isinstance(item, str) or not _SAFE_SOURCE_ID.fullmatch(item)
            for item in normalized
        ):
            raise ValueError("engineering error source identifier is invalid")
        return normalized


class RealEngineeringEnvelope(_EngineeringModel):
    schema_version: Literal[1] = 1
    datasheet: UnifiedDatasheetModel | None = None
    firmware_review: FirmwareReviewResult | None = None
    references: tuple[EngineeringSourceReference, ...] = ()
    errors: tuple[RealEngineeringError, ...] = ()

    @field_validator(
        "datasheet",
        "firmware_review",
        "references",
        "errors",
        mode="before",
    )
    @classmethod
    def isolate_values(cls, value: object) -> object:
        return copy.deepcopy(value)
