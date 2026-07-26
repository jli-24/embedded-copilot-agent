from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
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
_STRUCTURAL_SUMMARY = re.compile(
    r"^(?:TEXT|SOURCE_CODE) file structure: \d+ lines, \d+ characters\.$"
    r"|^(?:PDF|DATASHEET) file structure: \d+ pages\.$"
)


def _safe_identifier(value: object, *, field: str) -> str:
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
        or any(char in candidate for char in ("\r", "\n", "\x00"))
        or _ABSOLUTE_PATH.search(candidate)
        or _SENSITIVE_TEXT.search(candidate)
    ):
        raise ValueError(f"{field} is unsafe")
    return candidate


class _FileContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class FileType(StrEnum):
    UNKNOWN = "UNKNOWN"
    TEXT = "TEXT"
    SOURCE_CODE = "SOURCE_CODE"
    PDF = "PDF"
    DATASHEET = "DATASHEET"


class FileReferenceRequest(_FileContract):
    session_id: str
    file_id: str
    file_type: FileType
    instruction_summary: str

    @field_validator("session_id", "file_id", mode="before")
    @classmethod
    def validate_identifier(cls, value: object, info) -> str:
        return _safe_identifier(value, field=info.field_name)

    @field_validator("instruction_summary", mode="before")
    @classmethod
    def validate_instruction_summary(cls, value: object) -> str:
        return _safe_text(value, field="instruction_summary", max_length=512)


class FileReference(_FileContract):
    session_id: str
    file_id: str
    basename: str
    document_type: FileType
    size_bytes: int = Field(gt=0)
    relative_path: Path = Field(repr=False, exclude=True)

    @field_validator("session_id", "file_id", mode="before")
    @classmethod
    def validate_identifier(cls, value: object, info) -> str:
        return _safe_identifier(value, field=info.field_name)

    @field_validator("basename", mode="before")
    @classmethod
    def validate_basename(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("basename is invalid")
        candidate = value.strip()
        if (
            not candidate
            or len(candidate) > 255
            or "/" in candidate
            or "\\" in candidate
            or candidate in {".", ".."}
        ):
            raise ValueError("basename is invalid")
        return candidate

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, value: FileType) -> FileType:
        if value is FileType.UNKNOWN:
            raise ValueError("document type is unresolved")
        return value

    @field_validator("relative_path", mode="before")
    @classmethod
    def validate_relative_path(cls, value: object) -> Path:
        if not isinstance(value, (str, Path)):
            raise ValueError("relative path is invalid")
        raw = str(value)
        posix = PurePosixPath(raw)
        windows = PureWindowsPath(raw)
        if (
            not raw.strip()
            or posix.is_absolute()
            or windows.is_absolute()
            or windows.drive
            or raw.startswith(("/", "\\"))
            or any(part in {"", ".", ".."} for part in posix.parts)
            or any(part in {"", ".", ".."} for part in windows.parts)
        ):
            raise ValueError("relative path is invalid")
        return Path(raw)

    def __repr__(self) -> str:
        return (
            "FileReference("
            f"session_id={self.session_id!r}, "
            f"file_id={self.file_id!r}, "
            f"document_type={self.document_type.value!r}"
            ")"
        )

    def __str__(self) -> str:
        return self.__repr__()


class DocumentSummary(_FileContract):
    file_id: str
    document_type: FileType
    page_count: int | None = Field(default=None, ge=1)
    line_count: int | None = Field(default=None, ge=0)
    character_count: int | None = Field(default=None, ge=0)
    candidate: tuple[()] = ()

    @field_validator("file_id", mode="before")
    @classmethod
    def validate_file_id(cls, value: object) -> str:
        return _safe_identifier(value, field="file_id")

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, value: FileType) -> FileType:
        if value is FileType.UNKNOWN:
            raise ValueError("document type is unresolved")
        return value

    @model_validator(mode="after")
    def validate_counts(self) -> "DocumentSummary":
        if self.document_type in {FileType.PDF, FileType.DATASHEET}:
            if (
                self.page_count is None
                or self.line_count is not None
                or self.character_count is not None
            ):
                raise ValueError("PDF summary counts are invalid")
        elif (
            self.page_count is not None
            or self.line_count is None
            or self.character_count is None
        ):
            raise ValueError("text summary counts are invalid")
        return self


class FileIntelligenceResponse(_FileContract):
    output_type: Literal["reasoning_suggestion"] = "reasoning_suggestion"
    summary: str
    review_required: Literal[True] = True

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        candidate = _safe_text(value, field="summary", max_length=128)
        if not _STRUCTURAL_SUMMARY.fullmatch(candidate):
            raise ValueError("summary is not structural")
        return candidate


def format_document_summary(summary: DocumentSummary) -> str:
    if summary.document_type in {FileType.PDF, FileType.DATASHEET}:
        return (
            f"{summary.document_type.value} file structure: "
            f"{summary.page_count} pages."
        )
    return (
        f"{summary.document_type.value} file structure: "
        f"{summary.line_count} lines, {summary.character_count} characters."
    )
