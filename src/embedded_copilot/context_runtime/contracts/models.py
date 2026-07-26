from __future__ import annotations

import copy
import re
from collections.abc import Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_SAFE_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.-]{0,63}$")
_CONTEXT_ID = re.compile(r"^context:[a-f0-9]{24}$")
_ABSOLUTE_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file://|/(?:[^/\s]+/)+)",
    re.IGNORECASE,
)
_SENSITIVE_TEXT = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|(?:password|credential|secret)\s*[:=]"
    r"|(?:^|\s)sk-[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)

ComponentFamily = Literal["STM32", "ESP32", "nRF52", "RP2040"]
InterfaceName = Literal["UART", "SPI", "I2C", "USB", "CAN", "ADC", "PWM", "I2S"]
SectionName = Literal[
    "Pin Description",
    "Electrical Characteristics",
    "Absolute Maximum Ratings",
    "Functional Description",
    "Peripheral",
]


def _identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    candidate = value.strip()
    if not _SAFE_IDENTIFIER.fullmatch(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


def _safe_text(value: object, *, field: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    candidate = value.strip()
    if (
        not candidate
        or len(candidate) > max_length
        or any(character in candidate for character in ("\r", "\n", "\x00"))
        or _ABSOLUTE_PATH.search(candidate)
        or _SENSITIVE_TEXT.search(candidate)
    ):
        raise ValueError(f"{field} is unsafe")
    return candidate


class _ContextContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class ContextReferenceKind(StrEnum):
    FILE = "file"
    DATASHEET = "datasheet"
    VISION = "vision"


class ContextDocumentType(StrEnum):
    TEXT = "TEXT"
    SOURCE_CODE = "SOURCE_CODE"
    PDF = "PDF"
    DATASHEET = "DATASHEET"


class ContextImageType(StrEnum):
    SCHEMATIC = "schematic"
    PCB = "pcb"
    DATASHEET = "datasheet"
    DEBUG = "debug"
    UNKNOWN = "unknown"


class EngineeringContextRequest(_ContextContract):
    session_id: str
    task_intent: str
    reference_ids: tuple[str, ...] = Field(max_length=32)

    @field_validator("session_id", mode="before")
    @classmethod
    def validate_session_id(cls, value: object) -> str:
        return _identifier(value, field="session_id")

    @field_validator("task_intent", mode="before")
    @classmethod
    def validate_task_intent(cls, value: object) -> str:
        return _safe_text(value, field="task_intent", max_length=512)

    @field_validator("reference_ids", mode="before")
    @classmethod
    def validate_reference_ids(cls, value: object) -> object:
        if not isinstance(value, Sequence) or isinstance(
            value,
            (str, bytes, bytearray),
        ):
            return value
        references = tuple(
            _identifier(item, field="reference_id") for item in copy.deepcopy(value)
        )
        if len({item.casefold() for item in references}) != len(references):
            raise ValueError("reference_ids must be unique")
        return references


class ContextReference(_ContextContract):
    reference_id: str
    kind: ContextReferenceKind
    document_type: ContextDocumentType | None = None
    image_type: ContextImageType | None = None

    @field_validator("reference_id", mode="before")
    @classmethod
    def validate_reference_id(cls, value: object) -> str:
        return _identifier(value, field="reference_id")

    @model_validator(mode="after")
    def validate_metadata(self) -> "ContextReference":
        if self.kind is ContextReferenceKind.VISION:
            if self.image_type is None or self.document_type is not None:
                raise ValueError("vision reference metadata is invalid")
        elif self.document_type is None or self.image_type is not None:
            raise ValueError("file reference metadata is invalid")
        if self.kind is ContextReferenceKind.DATASHEET and self.document_type not in {
            ContextDocumentType.PDF,
            ContextDocumentType.DATASHEET,
        }:
            raise ValueError("datasheet reference type is invalid")
        return self


class FileContext(_ContextContract):
    file_id: str
    document_type: ContextDocumentType
    page_count: int | None = Field(default=None, ge=1)
    line_count: int | None = Field(default=None, ge=0)
    character_count: int | None = Field(default=None, ge=0)

    @field_validator("file_id", mode="before")
    @classmethod
    def validate_file_id(cls, value: object) -> str:
        return _identifier(value, field="file_id")

    @model_validator(mode="after")
    def validate_statistics(self) -> "FileContext":
        if self.document_type in {
            ContextDocumentType.PDF,
            ContextDocumentType.DATASHEET,
        }:
            if (
                self.page_count is None
                or self.line_count is not None
                or self.character_count is not None
            ):
                raise ValueError("PDF context statistics are invalid")
        elif (
            self.page_count is not None
            or self.line_count is None
            or self.character_count is None
        ):
            raise ValueError("text context statistics are invalid")
        return self


class ComponentContextCandidate(_ContextContract):
    semantics: Literal["candidate"] = "candidate"
    family: ComponentFamily
    model: str | None = None

    @field_validator("model", mode="before")
    @classmethod
    def validate_model(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("model must be a string")
        candidate = value.strip()
        if not _SAFE_MODEL.fullmatch(candidate):
            raise ValueError("model is invalid")
        return candidate


class InterfaceContextCandidate(_ContextContract):
    semantics: Literal["candidate"] = "candidate"
    name: InterfaceName


class SectionContextCandidate(_ContextContract):
    semantics: Literal["candidate"] = "candidate"
    name: SectionName


class DatasheetContext(_ContextContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    file_id: str
    component_candidate: ComponentContextCandidate | None = None
    interfaces: tuple[InterfaceContextCandidate, ...] = ()
    sections: tuple[SectionContextCandidate, ...] = ()

    @field_validator("file_id", mode="before")
    @classmethod
    def validate_file_id(cls, value: object) -> str:
        return _identifier(value, field="file_id")

    @model_validator(mode="after")
    def validate_unique_candidates(self) -> "DatasheetContext":
        if len({item.name for item in self.interfaces}) != len(self.interfaces):
            raise ValueError("interface candidates must be unique")
        if len({item.name for item in self.sections}) != len(self.sections):
            raise ValueError("section candidates must be unique")
        return self


class VisionContext(_ContextContract):
    reference_id: str
    image_type: ContextImageType

    @field_validator("reference_id", mode="before")
    @classmethod
    def validate_reference_id(cls, value: object) -> str:
        return _identifier(value, field="reference_id")


class EngineeringContextSummary(_ContextContract):
    context_id: str
    task_intent: str
    datasheets: tuple[DatasheetContext, ...] = ()
    files: tuple[FileContext, ...] = ()
    vision: tuple[VisionContext, ...] = ()

    @field_validator("context_id", mode="before")
    @classmethod
    def validate_context_id(cls, value: object) -> str:
        if not isinstance(value, str) or not _CONTEXT_ID.fullmatch(value):
            raise ValueError("context_id is invalid")
        return value

    @field_validator("task_intent", mode="before")
    @classmethod
    def validate_task_intent(cls, value: object) -> str:
        return _safe_text(value, field="task_intent", max_length=512)


class EngineeringContextResponse(_ContextContract):
    output_type: Literal["context_summary"] = "context_summary"
    context_summary: EngineeringContextSummary
    review_required: Literal[True] = True
