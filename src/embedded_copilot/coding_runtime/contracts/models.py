from __future__ import annotations

import copy
import hashlib
import json
import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from embedded_copilot.context_runtime.contracts import EngineeringContextResponse

_CONTEXT_ID = re.compile(r"^context:[a-f0-9]{24}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_RELATIVE_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/ -]{0,255}$")
_PIN = re.compile(r"^P[A-Z][0-9]{1,2}$")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_:.]*$")
_SOURCE_SUFFIXES = frozenset(
    {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hxx", ".py", ".ino", ".s"}
)
_MANIFEST_NAMES = frozenset(
    {"cmakelists.txt", "makefile", "prj.conf", "platformio.ini"}
)
_MARKER_SUFFIXES = frozenset({".ioc", ".ld", ".txt"})
_MAX_FILE_BYTES = 1024 * 1024
_MAX_TOTAL_BYTES = 8 * 1024 * 1024
_MAX_FILES = 256


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class CodeLanguage(StrEnum):
    C = "C"
    CPP = "CPP"
    PYTHON = "PYTHON"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class ProjectType(StrEnum):
    GENERIC = "GENERIC"
    STM32CUBEMX = "STM32CUBEMX"
    ESP_IDF = "ESP_IDF"
    ARDUINO = "ARDUINO"
    ZEPHYR = "ZEPHYR"


class BuildSystem(StrEnum):
    UNKNOWN = "UNKNOWN"
    CMAKE = "CMAKE"
    MAKE = "MAKE"
    ARDUINO = "ARDUINO"
    WEST = "WEST"
    PLATFORMIO = "PLATFORMIO"


class CompilerKind(StrEnum):
    GCC = "GCC"
    CLANG = "CLANG"
    ARM_NONE_EABI_GCC = "ARM_NONE_EABI_GCC"


class SymbolKind(StrEnum):
    FUNCTION = "function"
    CLASS = "class"
    STRUCT = "struct"
    MACRO = "macro"
    INCLUDE = "include"


class HardwareAccess(_Contract):
    resource: str
    operation: Literal["digital_write"]
    line: int = Field(ge=1)

    @field_validator("resource", mode="before")
    @classmethod
    def validate_resource(cls, value: object) -> str:
        if not isinstance(value, str) or not _PIN.fullmatch(value.strip().upper()):
            raise ValueError("hardware resource is invalid")
        return value.strip().upper()


class CodeFileInput(_Contract):
    path: str
    content: str

    @field_validator("path", mode="before")
    @classmethod
    def validate_path(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("path is invalid")
        path = value.strip().replace("\\", "/")
        name = path.rsplit("/", 1)[-1].casefold()
        suffix = "." + name.rsplit(".", 1)[1] if "." in name else ""
        if (
            not _RELATIVE_PATH.fullmatch(path)
            or ".." in path.split("/")
            or "\x00" in path
            or (
                suffix not in _SOURCE_SUFFIXES | _MARKER_SUFFIXES
                and name not in _MANIFEST_NAMES
            )
        ):
            raise ValueError("path is invalid")
        return path

    @field_validator("content", mode="before")
    @classmethod
    def validate_content(cls, value: object) -> str:
        if not isinstance(value, str) or "\x00" in value:
            raise ValueError("content is invalid")
        if len(value.encode("utf-8")) > _MAX_FILE_BYTES:
            raise ValueError("content exceeds file limit")
        return copy.deepcopy(value)


class CodeFileSummary(_Contract):
    path: str
    language: CodeLanguage
    content_sha256: str
    line_count: int = Field(ge=0)
    hardware_accesses: tuple[HardwareAccess, ...] = ()


class CodeSymbol(_Contract):
    file: str
    line: int = Field(ge=1)
    kind: SymbolKind
    name: str

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value.strip()):
            raise ValueError("symbol name is invalid")
        return value.strip()


class CodeDependency(_Contract):
    file: str
    line: int = Field(ge=1)
    name: str
    kind: Literal["include", "import", "manifest"]

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 160:
            raise ValueError("dependency name is invalid")
        return value.strip()


class ParseIssue(_Contract):
    file: str
    line: int = Field(ge=1)
    message: Literal["syntax error"]


def _snapshot_payload(
    *,
    schema_version: str,
    context_id: str,
    project_type: ProjectType,
    language: CodeLanguage,
    frameworks: tuple[str, ...],
    build_system: BuildSystem,
    files: tuple[CodeFileSummary, ...],
    symbols: tuple[CodeSymbol, ...],
    dependencies: tuple[CodeDependency, ...],
) -> dict[str, object]:
    return {
        "build_system": build_system.value,
        "context_id": context_id,
        "dependencies": [item.model_dump(mode="json") for item in dependencies],
        "files": [item.model_dump(mode="json") for item in files],
        "frameworks": list(frameworks),
        "language": language.value,
        "project_type": project_type.value,
        "schema_version": schema_version,
        "symbols": [item.model_dump(mode="json") for item in symbols],
    }


def snapshot_fingerprint(**kwargs: object) -> str:
    encoded = json.dumps(
        _snapshot_payload(**kwargs),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class FrozenCodeContextSnapshot(_Contract):
    schema_version: Literal["1.0"] = "1.0"
    snapshot_fingerprint: str
    context_id: str
    project_type: ProjectType
    language: CodeLanguage
    frameworks: tuple[str, ...] = ()
    build_system: BuildSystem
    files: tuple[CodeFileSummary, ...] = ()
    symbols: tuple[CodeSymbol, ...] = ()
    dependencies: tuple[CodeDependency, ...] = ()

    @field_validator("context_id", mode="before")
    @classmethod
    def validate_context_id(cls, value: object) -> str:
        if not isinstance(value, str) or not _CONTEXT_ID.fullmatch(value.strip()):
            raise ValueError("context_id is invalid")
        return value.strip()

    @field_validator("snapshot_fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value.strip()):
            raise ValueError("snapshot_fingerprint is invalid")
        return value.strip()

    @model_validator(mode="after")
    def validate_fingerprint_match(self) -> "FrozenCodeContextSnapshot":
        expected = snapshot_fingerprint(
            schema_version=self.schema_version,
            context_id=self.context_id,
            project_type=self.project_type,
            language=self.language,
            frameworks=self.frameworks,
            build_system=self.build_system,
            files=self.files,
            symbols=self.symbols,
            dependencies=self.dependencies,
        )
        if self.snapshot_fingerprint != expected:
            raise ValueError("snapshot_fingerprint does not match snapshot")
        return self


class ProjectAnalysisRequest(_Contract):
    context_id: str
    files: tuple[CodeFileInput, ...] = Field(min_length=1, max_length=_MAX_FILES)

    @field_validator("context_id", mode="before")
    @classmethod
    def validate_context_id(cls, value: object) -> str:
        return FrozenCodeContextSnapshot.validate_context_id(value)

    @model_validator(mode="after")
    def validate_files(self) -> "ProjectAnalysisRequest":
        paths = tuple(item.path.casefold() for item in self.files)
        if len(paths) != len(set(paths)):
            raise ValueError("duplicate paths are invalid")
        if (
            sum(len(item.content.encode("utf-8")) for item in self.files)
            > _MAX_TOTAL_BYTES
        ):
            raise ValueError("content exceeds project limit")
        return self


class ProjectSummary(_Contract):
    project_type: ProjectType
    frameworks: tuple[str, ...] = ()
    build_system: BuildSystem
    marker_candidates: tuple[str, ...] = ()


class ProjectAnalysisResponse(_Contract):
    snapshot: FrozenCodeContextSnapshot
    project_summary: ProjectSummary
    parse_issues: tuple[ParseIssue, ...] = ()


class BuildAnalysisRequest(_Contract):
    compiler: CompilerKind
    log: str

    @field_validator("log", mode="before")
    @classmethod
    def validate_log(cls, value: object) -> str:
        if (
            not isinstance(value, str)
            or "\x00" in value
            or len(value.encode("utf-8")) > 512 * 1024
        ):
            raise ValueError("build log is invalid")
        return copy.deepcopy(value)


class BuildIssue(_Contract):
    error_type: Literal["COMPILER_ERROR", "LINKER_ERROR"]
    file: str | None = None
    line: int | None = Field(default=None, ge=1)
    evidence: str
    suggestion: Literal[
        "Review the observed diagnostic against the declared source and build configuration."
    ]


class BuildAnalysisResponse(_Contract):
    issues: tuple[BuildIssue, ...] = ()


class DiffReviewRequest(_Contract):
    diff: str

    @field_validator("diff", mode="before")
    @classmethod
    def validate_diff(cls, value: object) -> str:
        if (
            not isinstance(value, str)
            or "\x00" in value
            or len(value.encode("utf-8")) > 1024 * 1024
        ):
            raise ValueError("diff is invalid")
        if "diff --git " not in value or "@@" not in value or "Binary files" in value:
            raise ValueError("diff must be a non-binary unified diff")
        return copy.deepcopy(value)


class ChangeCandidate(_Contract):
    category: Literal[
        "API_CHANGE", "POTENTIAL_BUG", "MCU_RESOURCE", "PERIPHERAL_CONFIGURATION"
    ]
    description: str


class ChangeReview(_Contract):
    candidate_semantics: Literal["unverified"] = "unverified"
    candidates: tuple[ChangeCandidate, ...] = ()


class PinFunctionCandidate(_Contract):
    reference_id: str
    pin: str
    function: str

    @field_validator("reference_id", mode="before")
    @classmethod
    def validate_reference_id(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 160:
            raise ValueError("reference_id is invalid")
        return value.strip()

    @field_validator("pin", mode="before")
    @classmethod
    def validate_pin(cls, value: object) -> str:
        if not isinstance(value, str) or not _PIN.fullmatch(value.strip().upper()):
            raise ValueError("pin is invalid")
        return value.strip().upper()

    @field_validator("function", mode="before")
    @classmethod
    def validate_function(cls, value: object) -> str:
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value.strip()):
            raise ValueError("function is invalid")
        return value.strip()


class HardwareSoftwareFusionRequest(_Contract):
    snapshot: FrozenCodeContextSnapshot
    engineering_context: EngineeringContextResponse
    pin_candidates: tuple[PinFunctionCandidate, ...] = Field(max_length=128)

    @model_validator(mode="after")
    def validate_context_binding(self) -> "HardwareSoftwareFusionRequest":
        if (
            self.snapshot.context_id
            != self.engineering_context.context_summary.context_id
        ):
            raise ValueError("snapshot context does not match engineering context")
        reference_ids = {
            item.file_id for item in self.engineering_context.context_summary.datasheets
        }
        if any(item.reference_id not in reference_ids for item in self.pin_candidates):
            raise ValueError("pin candidate is not bound to a datasheet reference")
        return self


class HardwareSoftwareConflictCandidate(_Contract):
    pin: str
    candidate_function: str
    reference_id: str
    description: Literal[
        "Hardware/software relationship candidate requires engineer verification."
    ]


class HardwareSoftwareFusionResponse(_Contract):
    candidate_semantics: Literal["unverified"] = "unverified"
    conflict_candidates: tuple[HardwareSoftwareConflictCandidate, ...] = ()
