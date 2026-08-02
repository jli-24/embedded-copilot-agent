"""Immutable contracts for proposal-only Firmware Engineering."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
_FINGERPRINT = re.compile(r"^sha256:[0-9a-f]{64}$")
_HTTPS_REFERENCE = re.compile(r"^https://[^\s?#]{1,480}$")
_ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|file://|/(?:[^\s/]+/)+)")
_SENSITIVE = re.compile(
    r"(?:password|credential|authorization|private[_ -]?key|api[_ -]?key|token)",
    re.IGNORECASE,
)


class _FirmwareContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        revalidate_instances="always",
    )


def _identifier(value: object, *, field: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if _IDENTIFIER.fullmatch(candidate) is None:
        raise ValueError(f"{field} is invalid")
    return candidate


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _safe_text(value: object, *, field: str, maximum: int = 256) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if not candidate or len(candidate) > maximum:
        raise ValueError(f"{field} is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in candidate):
        raise ValueError(f"{field} is invalid")
    if _ABSOLUTE_PATH.search(candidate) or _SENSITIVE.search(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


def _tuple(value: object, *, field: str) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def _identifiers(value: object, *, field: str) -> tuple[str, ...]:
    values = _tuple(value, field=field)
    checked = tuple(_identifier(item, field=field) for item in values)
    if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
        raise ValueError(f"{field} must be sorted and unique")
    return checked


def _references(value: object) -> tuple[str, ...]:
    values = _tuple(value, field="reference_ids")
    checked: list[str] = []
    for item in values:
        if type(item) is not str:
            raise ValueError("reference_ids are invalid")
        candidate = unicodedata.normalize("NFC", item.strip())
        if _IDENTIFIER.fullmatch(candidate) is None and not (
            _HTTPS_REFERENCE.fullmatch(candidate) is not None
            and "?" not in candidate
            and "#" not in candidate
        ):
            raise ValueError("reference_ids are invalid")
        checked.append(candidate)
    result = tuple(checked)
    if result != tuple(sorted(result)) or len(result) != len(set(result)):
        raise ValueError("reference_ids must be sorted and unique")
    return result


def _fingerprint_value(value: object) -> str:
    if type(value) is not str or _FINGERPRINT.fullmatch(value) is None:
        raise ValueError("fingerprint is invalid")
    return value


def _utc(value: object, *, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field} must be timezone aware")
    if value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone aware")
    return value.astimezone(UTC)


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        encoded = value.astimezone(UTC).isoformat()
        return f"{encoded[:-6]}Z"
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        _jsonable(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _projection_fingerprint(kind: str, **values: object) -> str:
    return _fingerprint({"kind": kind, **values})


class FirmwarePlatformProfile(StrEnum):
    ESP_IDF_FREERTOS = "ESP_IDF_FREERTOS"
    STM32_RTOS = "STM32_RTOS"
    UNRESOLVED = "UNRESOLVED"


class FirmwareBuildSystem(StrEnum):
    ESP_IDF = "ESP_IDF"
    CMAKE = "CMAKE"
    UNRESOLVED = "UNRESOLVED"


class FirmwareToolchainRequirement(StrEnum):
    ESP_IDF_TOOLCHAIN = "ESP_IDF_TOOLCHAIN"
    ARM_GNU_TOOLCHAIN = "ARM_GNU_TOOLCHAIN"
    UNRESOLVED = "UNRESOLVED"


class FirmwarePlatformStatus(StrEnum):
    PROPOSED = "PROPOSED"
    SUPPORTED = "SUPPORTED"
    UNRESOLVED = "UNRESOLVED"


class FirmwareProposalItemStatus(StrEnum):
    PROPOSED = "PROPOSED"
    UNRESOLVED = "UNRESOLVED"
    BLOCKED = "BLOCKED"


class FirmwareModuleLayer(StrEnum):
    BSP = "BSP"
    DRIVERS = "DRIVERS"
    MIDDLEWARE = "MIDDLEWARE"
    APPLICATION = "APPLICATION"
    TESTS = "TESTS"


class FirmwareDriverType(StrEnum):
    BSP_SUPPORT = "BSP_SUPPORT"
    COMPONENT_DRIVER = "COMPONENT_DRIVER"
    INTERFACE_ADAPTER = "INTERFACE_ADAPTER"


class FirmwareTaskType(StrEnum):
    CAMERA = "CAMERA"
    NETWORK = "NETWORK"
    STORAGE = "STORAGE"


class FirmwarePriorityRecommendation(StrEnum):
    UNRESOLVED = "UNRESOLVED"


class FirmwareDiagnosticCategory(StrEnum):
    COMPILE_ERROR = "COMPILE_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    MEMORY_ISSUE = "MEMORY_ISSUE"


class FirmwareBuildArtifactType(StrEnum):
    FIRMWARE_IMAGE = "FIRMWARE_IMAGE"
    UNRESOLVED = "UNRESOLVED"


class BuildArtifactStatus(StrEnum):
    UNAVAILABLE = "UNAVAILABLE"


class FirmwareExecutionPrerequisite(StrEnum):
    TOOL_BINDING = "TOOL_BINDING"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    VERIFICATION = "VERIFICATION"


class FirmwareFindingCode(StrEnum):
    PLATFORM_UNRESOLVED = "PLATFORM_UNRESOLVED"
    HARDWARE_CONFLICT_REQUIRES_REVIEW = "HARDWARE_CONFLICT_REQUIRES_REVIEW"
    DRIVER_BINDING_UNRESOLVED = "DRIVER_BINDING_UNRESOLVED"
    INTERFACE_DETAIL_UNRESOLVED = "INTERFACE_DETAIL_UNRESOLVED"
    TASK_PRIORITY_UNRESOLVED = "TASK_PRIORITY_UNRESOLVED"
    BUILD_CONFIGURATION_UNRESOLVED = "BUILD_CONFIGURATION_UNRESOLVED"
    DEBUG_EVIDENCE_REQUIRED = "DEBUG_EVIDENCE_REQUIRED"
    EXECUTION_NOT_AVAILABLE = "EXECUTION_NOT_AVAILABLE"


class FirmwareFindingSeverity(StrEnum):
    BLOCKING = "BLOCKING"
    REVIEW = "REVIEW"


def firmware_platform_fingerprint(
    *,
    project_id: str,
    requirement_fingerprint: str,
    hardware_proposal_fingerprint: str,
    context_fingerprint: str,
    platform_profile: FirmwarePlatformProfile,
    build_system: FirmwareBuildSystem,
    toolchain_requirement: FirmwareToolchainRequirement,
    status: FirmwarePlatformStatus,
    evidence_ids: tuple[str, ...],
) -> str:
    return _projection_fingerprint(
        "FirmwarePlatformProjection",
        project_id=project_id,
        requirement_fingerprint=requirement_fingerprint,
        hardware_proposal_fingerprint=hardware_proposal_fingerprint,
        context_fingerprint=context_fingerprint,
        platform_profile=platform_profile,
        build_system=build_system,
        toolchain_requirement=toolchain_requirement,
        status=status,
        evidence_ids=evidence_ids,
    )


class FirmwarePlatformProjection(_FirmwareContract):
    project_id: str
    requirement_fingerprint: str
    hardware_proposal_fingerprint: str
    context_fingerprint: str
    platform_profile: FirmwarePlatformProfile
    build_system: FirmwareBuildSystem
    toolchain_requirement: FirmwareToolchainRequirement
    status: FirmwarePlatformStatus
    evidence_ids: tuple[str, ...]
    fingerprint: str

    _project_id = field_validator("project_id")(
        lambda value: _identifier(value, field="project_id")
    )
    _requirement_fingerprint = field_validator("requirement_fingerprint")(
        _fingerprint_value
    )
    _hardware_fingerprint = field_validator("hardware_proposal_fingerprint")(
        _fingerprint_value
    )
    _context_fingerprint = field_validator("context_fingerprint")(_fingerprint_value)
    _evidence_ids = field_validator("evidence_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_ids")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_projection(self) -> FirmwarePlatformProjection:
        allowed = {
            FirmwarePlatformProfile.ESP_IDF_FREERTOS: (
                FirmwareBuildSystem.ESP_IDF,
                FirmwareToolchainRequirement.ESP_IDF_TOOLCHAIN,
            ),
            FirmwarePlatformProfile.STM32_RTOS: (
                FirmwareBuildSystem.CMAKE,
                FirmwareToolchainRequirement.ARM_GNU_TOOLCHAIN,
            ),
            FirmwarePlatformProfile.UNRESOLVED: (
                FirmwareBuildSystem.UNRESOLVED,
                FirmwareToolchainRequirement.UNRESOLVED,
            ),
        }
        if (self.build_system, self.toolchain_requirement) != allowed[
            self.platform_profile
        ]:
            raise ValueError("platform combination is invalid")
        if self.status is FirmwarePlatformStatus.SUPPORTED and not self.evidence_ids:
            raise ValueError("supported platform requires evidence")
        if self.status is FirmwarePlatformStatus.UNRESOLVED and (
            self.platform_profile is not FirmwarePlatformProfile.UNRESOLVED
            or self.evidence_ids
        ):
            raise ValueError("unresolved platform binding is invalid")
        if self.status is FirmwarePlatformStatus.PROPOSED and self.evidence_ids:
            raise ValueError("proposed platform cannot claim verified evidence")
        expected = firmware_platform_fingerprint(
            project_id=self.project_id,
            requirement_fingerprint=self.requirement_fingerprint,
            hardware_proposal_fingerprint=self.hardware_proposal_fingerprint,
            context_fingerprint=self.context_fingerprint,
            platform_profile=self.platform_profile,
            build_system=self.build_system,
            toolchain_requirement=self.toolchain_requirement,
            status=self.status,
            evidence_ids=self.evidence_ids,
        )
        if self.fingerprint != expected:
            raise ValueError("platform fingerprint mismatch")
        return self


class FirmwareEvidenceTrace(_FirmwareContract):
    evidence_id: str
    source_type: str
    reference_ids: tuple[str, ...]
    source_fingerprint: str

    _evidence_id = field_validator("evidence_id")(
        lambda value: _identifier(value, field="evidence_id")
    )
    _source_type = field_validator("source_type")(
        lambda value: _token(value, field="source_type")
    )
    _reference_ids = field_validator("reference_ids", mode="before")(_references)
    _source_fingerprint = field_validator("source_fingerprint")(_fingerprint_value)


class FirmwareArchitectureModule(_FirmwareContract):
    layer: FirmwareModuleLayer
    responsibility: str
    component_references: tuple[str, ...] = ()
    interface_references: tuple[str, ...] = ()
    status: FirmwareProposalItemStatus

    _responsibility = field_validator("responsibility")(
        lambda value: _token(value, field="responsibility")
    )
    _component_references = field_validator("component_references", mode="before")(
        lambda value: _identifiers(value, field="component_references")
    )
    _interface_references = field_validator("interface_references", mode="before")(
        lambda value: _identifiers(value, field="interface_references")
    )


class FirmwareArchitectureProposal(_FirmwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    modules: tuple[FirmwareArchitectureModule, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("modules", mode="before")
    @classmethod
    def validate_modules_tuple(cls, value: object) -> object:
        return _tuple(value, field="modules")

    @model_validator(mode="after")
    def validate_projection(self) -> FirmwareArchitectureProposal:
        if tuple(item.layer for item in self.modules) != tuple(FirmwareModuleLayer):
            raise ValueError("firmware architecture layers are invalid")
        expected = _projection_fingerprint(
            "FirmwareArchitectureProposal", modules=self.modules
        )
        if self.fingerprint != expected:
            raise ValueError("firmware architecture fingerprint mismatch")
        return self


class FirmwareDriverRequirement(_FirmwareContract):
    driver_reference: str
    driver_type: FirmwareDriverType
    responsibility: str
    component_reference: str | None = None
    interface_references: tuple[str, ...] = ()
    dependency_references: tuple[str, ...] = ()
    status: FirmwareProposalItemStatus
    evidence_ids: tuple[str, ...] = ()

    _driver_reference = field_validator("driver_reference")(
        lambda value: _identifier(value, field="driver_reference")
    )
    _responsibility = field_validator("responsibility")(
        lambda value: _token(value, field="responsibility")
    )

    @field_validator("component_reference")
    @classmethod
    def validate_component_reference(cls, value: object) -> str | None:
        if value is None:
            return None
        return _identifier(value, field="component_reference")

    @field_validator(
        "interface_references", "dependency_references", "evidence_ids", mode="before"
    )
    @classmethod
    def validate_identifier_tuples(cls, value: object, info) -> tuple[str, ...]:
        return _identifiers(value, field=info.field_name)


class DriverDesignProposal(_FirmwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    drivers: tuple[FirmwareDriverRequirement, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("drivers", mode="before")
    @classmethod
    def validate_drivers_tuple(cls, value: object) -> object:
        return _tuple(value, field="drivers")

    @model_validator(mode="after")
    def validate_projection(self) -> DriverDesignProposal:
        keys = tuple(item.driver_reference for item in self.drivers)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("driver requirements must be sorted and unique")
        expected = _projection_fingerprint("DriverDesignProposal", drivers=self.drivers)
        if self.fingerprint != expected:
            raise ValueError("driver design fingerprint mismatch")
        return self


class FirmwareTaskProposal(_FirmwareContract):
    task_type: FirmwareTaskType
    responsibility: str
    driver_references: tuple[str, ...]
    dependency_tasks: tuple[FirmwareTaskType, ...] = ()
    priority_recommendation: Literal[FirmwarePriorityRecommendation.UNRESOLVED] = (
        FirmwarePriorityRecommendation.UNRESOLVED
    )
    stack_size_bytes: None = None
    status: FirmwareProposalItemStatus

    _responsibility = field_validator("responsibility")(
        lambda value: _token(value, field="responsibility")
    )
    _driver_references = field_validator("driver_references", mode="before")(
        lambda value: _identifiers(value, field="driver_references")
    )

    @field_validator("dependency_tasks", mode="before")
    @classmethod
    def validate_dependency_tuple(cls, value: object) -> object:
        return _tuple(value, field="dependency_tasks")


class RTOSTaskArchitectureProposal(_FirmwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    platform_profile: FirmwarePlatformProfile
    tasks: tuple[FirmwareTaskProposal, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("tasks", mode="before")
    @classmethod
    def validate_tasks_tuple(cls, value: object) -> object:
        return _tuple(value, field="tasks")

    @model_validator(mode="after")
    def validate_projection(self) -> RTOSTaskArchitectureProposal:
        order = {item: index for index, item in enumerate(FirmwareTaskType)}
        keys = tuple(order[item.task_type] for item in self.tasks)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("firmware tasks must be sorted and unique")
        expected = _projection_fingerprint(
            "RTOSTaskArchitectureProposal",
            platform_profile=self.platform_profile,
            tasks=self.tasks,
        )
        if self.fingerprint != expected:
            raise ValueError("task architecture fingerprint mismatch")
        return self


class FirmwareInterfaceContract(_FirmwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    hardware_interface_id: str
    protocol: str
    component_reference: str | None = None
    evidence_ids: tuple[str, ...] = ()
    pin_bindings: tuple[str, ...] = ()
    register_bindings: tuple[str, ...] = ()
    clock_configuration: None = None
    memory_layout: None = None
    status: Literal[FirmwareProposalItemStatus.UNRESOLVED] = (
        FirmwareProposalItemStatus.UNRESOLVED
    )

    _hardware_interface_id = field_validator("hardware_interface_id")(
        lambda value: _identifier(value, field="hardware_interface_id")
    )
    _protocol = field_validator("protocol")(
        lambda value: _token(value, field="protocol")
    )

    @field_validator("component_reference")
    @classmethod
    def validate_component_reference(cls, value: object) -> str | None:
        if value is None:
            return None
        return _identifier(value, field="component_reference")

    _evidence_ids = field_validator("evidence_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_ids")
    )

    @field_validator("pin_bindings", "register_bindings", mode="before")
    @classmethod
    def validate_unresolved_bindings(cls, value: object, info) -> tuple[str, ...]:
        values = _tuple(value, field=info.field_name)
        if values:
            raise ValueError(f"{info.field_name} must remain unresolved")
        return ()


class FirmwareInterfaceContractProposal(_FirmwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    contracts: tuple[FirmwareInterfaceContract, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("contracts", mode="before")
    @classmethod
    def validate_contracts_tuple(cls, value: object) -> object:
        return _tuple(value, field="contracts")

    @model_validator(mode="after")
    def validate_projection(self) -> FirmwareInterfaceContractProposal:
        keys = tuple(item.hardware_interface_id for item in self.contracts)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("firmware interfaces must be sorted and unique")
        expected = _projection_fingerprint(
            "FirmwareInterfaceContractProposal", contracts=self.contracts
        )
        if self.fingerprint != expected:
            raise ValueError("firmware interface fingerprint mismatch")
        return self


class CodeGenerationIntent(_FirmwareContract):
    module_group: FirmwareModuleLayer
    intent_code: str
    responsibility: str
    dependency_references: tuple[str, ...] = ()

    _intent_code = field_validator("intent_code")(
        lambda value: _token(value, field="intent_code")
    )
    _responsibility = field_validator("responsibility")(
        lambda value: _token(value, field="responsibility")
    )
    _dependency_references = field_validator("dependency_references", mode="before")(
        lambda value: _identifiers(value, field="dependency_references")
    )


class CodeGenerationPlan(_FirmwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    intents: tuple[CodeGenerationIntent, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("intents", mode="before")
    @classmethod
    def validate_intents_tuple(cls, value: object) -> object:
        return _tuple(value, field="intents")

    @model_validator(mode="after")
    def validate_projection(self) -> CodeGenerationPlan:
        if tuple(item.module_group for item in self.intents) != tuple(
            FirmwareModuleLayer
        ):
            raise ValueError("code generation intents are invalid")
        expected = _projection_fingerprint("CodeGenerationPlan", intents=self.intents)
        if self.fingerprint != expected:
            raise ValueError("code generation fingerprint mismatch")
        return self


class BuildProposal(_FirmwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    platform_profile: FirmwarePlatformProfile
    build_system: FirmwareBuildSystem
    toolchain_requirement: FirmwareToolchainRequirement
    expected_artifact_type: FirmwareBuildArtifactType
    artifact_status: Literal[BuildArtifactStatus.UNAVAILABLE] = (
        BuildArtifactStatus.UNAVAILABLE
    )
    command_available: Literal[False] = False
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_projection(self) -> BuildProposal:
        expected = _projection_fingerprint(
            "BuildProposal",
            platform_profile=self.platform_profile,
            build_system=self.build_system,
            toolchain_requirement=self.toolchain_requirement,
            expected_artifact_type=self.expected_artifact_type,
            artifact_status=self.artifact_status,
            command_available=self.command_available,
        )
        if self.fingerprint != expected:
            raise ValueError("build proposal fingerprint mismatch")
        return self


class FirmwareDiagnosticStrategy(_FirmwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    category: FirmwareDiagnosticCategory
    check_codes: tuple[str, ...]
    evidence_ids: tuple[str, ...]

    @field_validator("check_codes", mode="before")
    @classmethod
    def validate_check_codes(cls, value: object) -> tuple[str, ...]:
        values = _tuple(value, field="check_codes")
        checked = tuple(_token(item, field="check_code") for item in values)
        if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
            raise ValueError("check_codes must be sorted and unique")
        return checked

    _evidence_ids = field_validator("evidence_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_ids")
    )


class DebugStrategyProposal(_FirmwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    strategies: tuple[FirmwareDiagnosticStrategy, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("strategies", mode="before")
    @classmethod
    def validate_strategies_tuple(cls, value: object) -> object:
        return _tuple(value, field="strategies")

    @model_validator(mode="after")
    def validate_projection(self) -> DebugStrategyProposal:
        order = {item: index for index, item in enumerate(FirmwareDiagnosticCategory)}
        keys = tuple(order[item.category] for item in self.strategies)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("diagnostic strategies must be sorted and unique")
        expected = _projection_fingerprint(
            "DebugStrategyProposal", strategies=self.strategies
        )
        if self.fingerprint != expected:
            raise ValueError("debug strategy fingerprint mismatch")
        return self


class FirmwareReviewFinding(_FirmwareContract):
    code: FirmwareFindingCode
    severity: FirmwareFindingSeverity
    subject_reference: str
    evidence_ids: tuple[str, ...] = ()

    _subject_reference = field_validator("subject_reference")(
        lambda value: _identifier(value, field="subject_reference")
    )
    _evidence_ids = field_validator("evidence_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_ids")
    )


class FirmwareReviewProjection(_FirmwareContract):
    proposal_id: str
    hardware_proposal_fingerprint: str
    requirement_fingerprint: str
    context_fingerprint: str
    module_count: int = Field(ge=0)
    driver_count: int = Field(ge=0)
    task_count: int = Field(ge=0)
    interface_count: int = Field(ge=0)
    unresolved_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    findings: tuple[FirmwareReviewFinding, ...]
    finding_codes: tuple[FirmwareFindingCode, ...]
    review_required: Literal[True] = True
    fingerprint: str

    _proposal_id = field_validator("proposal_id")(
        lambda value: _identifier(value, field="proposal_id")
    )
    _hardware_fingerprint = field_validator("hardware_proposal_fingerprint")(
        _fingerprint_value
    )
    _requirement_fingerprint = field_validator("requirement_fingerprint")(
        _fingerprint_value
    )
    _context_fingerprint = field_validator("context_fingerprint")(_fingerprint_value)
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator(
        "module_count",
        "driver_count",
        "task_count",
        "interface_count",
        "unresolved_count",
        "evidence_count",
    )
    @classmethod
    def validate_count(cls, value: int, info) -> int:
        if type(value) is not int or value < 0:
            raise ValueError(f"{info.field_name} is invalid")
        return value

    @field_validator("findings", "finding_codes", mode="before")
    @classmethod
    def validate_tuple_fields(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_projection(self) -> FirmwareReviewProjection:
        keys = tuple(
            (item.code.value, item.subject_reference) for item in self.findings
        )
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("firmware findings must be sorted and unique")
        expected_codes = tuple(
            sorted({item.code for item in self.findings}, key=lambda item: item.value)
        )
        if self.finding_codes != expected_codes:
            raise ValueError("firmware finding codes are invalid")
        expected = _projection_fingerprint(
            "FirmwareReviewProjection",
            proposal_id=self.proposal_id,
            hardware_proposal_fingerprint=self.hardware_proposal_fingerprint,
            requirement_fingerprint=self.requirement_fingerprint,
            context_fingerprint=self.context_fingerprint,
            module_count=self.module_count,
            driver_count=self.driver_count,
            task_count=self.task_count,
            interface_count=self.interface_count,
            unresolved_count=self.unresolved_count,
            evidence_count=self.evidence_count,
            findings=self.findings,
            finding_codes=self.finding_codes,
            review_required=self.review_required,
        )
        if self.fingerprint != expected:
            raise ValueError("firmware review fingerprint mismatch")
        return self


class FirmwareExecutionContract(_FirmwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    proposal_id: str
    hardware_proposal_fingerprint: str
    requirement_fingerprint: str
    context_fingerprint: str
    build_proposal_fingerprint: str
    debug_strategy_fingerprint: str
    prerequisites: tuple[FirmwareExecutionPrerequisite, ...]
    execution_state: Literal["PROPOSAL_ONLY"] = "PROPOSAL_ONLY"
    execution_available: Literal[False] = False
    artifact_status: Literal[BuildArtifactStatus.UNAVAILABLE] = (
        BuildArtifactStatus.UNAVAILABLE
    )
    review_required: Literal[True] = True
    fingerprint: str

    _proposal_id = field_validator("proposal_id")(
        lambda value: _identifier(value, field="proposal_id")
    )
    _hardware_fingerprint = field_validator("hardware_proposal_fingerprint")(
        _fingerprint_value
    )
    _requirement_fingerprint = field_validator("requirement_fingerprint")(
        _fingerprint_value
    )
    _context_fingerprint = field_validator("context_fingerprint")(_fingerprint_value)
    _build_fingerprint = field_validator("build_proposal_fingerprint")(
        _fingerprint_value
    )
    _debug_fingerprint = field_validator("debug_strategy_fingerprint")(
        _fingerprint_value
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("prerequisites", mode="before")
    @classmethod
    def validate_prerequisite_tuple(cls, value: object) -> object:
        return _tuple(value, field="prerequisites")

    @model_validator(mode="after")
    def validate_projection(self) -> FirmwareExecutionContract:
        if self.prerequisites != tuple(FirmwareExecutionPrerequisite):
            raise ValueError("execution prerequisites are invalid")
        expected = _projection_fingerprint(
            "FirmwareExecutionContract",
            proposal_id=self.proposal_id,
            hardware_proposal_fingerprint=self.hardware_proposal_fingerprint,
            requirement_fingerprint=self.requirement_fingerprint,
            context_fingerprint=self.context_fingerprint,
            build_proposal_fingerprint=self.build_proposal_fingerprint,
            debug_strategy_fingerprint=self.debug_strategy_fingerprint,
            prerequisites=self.prerequisites,
            execution_state=self.execution_state,
            execution_available=self.execution_available,
            artifact_status=self.artifact_status,
            review_required=self.review_required,
        )
        if self.fingerprint != expected:
            raise ValueError("execution contract fingerprint mismatch")
        return self


def firmware_engineering_proposal_fingerprint(
    *,
    proposal_id: str,
    project_id: str,
    hardware_proposal_fingerprint: str,
    requirement_fingerprint: str,
    plan_fingerprint: str,
    context_fingerprint: str,
    platform: FirmwarePlatformProjection,
    architecture: FirmwareArchitectureProposal,
    driver_design: DriverDesignProposal,
    task_architecture: RTOSTaskArchitectureProposal,
    interface_contracts: FirmwareInterfaceContractProposal,
    code_generation: CodeGenerationPlan,
    build: BuildProposal,
    debug_strategy: DebugStrategyProposal,
    execution_contract: FirmwareExecutionContract,
    evidence_trace: tuple[FirmwareEvidenceTrace, ...],
    review: FirmwareReviewProjection,
    proposed_at: datetime,
    candidate_semantics: str,
    review_required: bool,
) -> str:
    return _projection_fingerprint(
        "FirmwareEngineeringProposal",
        proposal_id=proposal_id,
        project_id=project_id,
        hardware_proposal_fingerprint=hardware_proposal_fingerprint,
        requirement_fingerprint=requirement_fingerprint,
        plan_fingerprint=plan_fingerprint,
        context_fingerprint=context_fingerprint,
        platform=platform,
        architecture=architecture,
        driver_design=driver_design,
        task_architecture=task_architecture,
        interface_contracts=interface_contracts,
        code_generation=code_generation,
        build=build,
        debug_strategy=debug_strategy,
        execution_contract=execution_contract,
        evidence_trace=evidence_trace,
        review=review,
        proposed_at=proposed_at,
        candidate_semantics=candidate_semantics,
        review_required=review_required,
    )


class FirmwareEngineeringProposal(_FirmwareContract):
    schema_version: Literal["1.0"] = "1.0"
    proposal_id: str
    project_id: str
    hardware_proposal_fingerprint: str
    requirement_fingerprint: str
    plan_fingerprint: str
    context_fingerprint: str
    platform: FirmwarePlatformProjection
    architecture: FirmwareArchitectureProposal
    driver_design: DriverDesignProposal
    task_architecture: RTOSTaskArchitectureProposal
    interface_contracts: FirmwareInterfaceContractProposal
    code_generation: CodeGenerationPlan
    build: BuildProposal
    debug_strategy: DebugStrategyProposal
    execution_contract: FirmwareExecutionContract
    evidence_trace: tuple[FirmwareEvidenceTrace, ...]
    review: FirmwareReviewProjection
    proposed_at: datetime
    candidate_semantics: Literal["unverified"] = "unverified"
    review_required: Literal[True] = True
    fingerprint: str

    @field_validator("proposal_id", "project_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _hardware_fingerprint = field_validator("hardware_proposal_fingerprint")(
        _fingerprint_value
    )
    _requirement_fingerprint = field_validator("requirement_fingerprint")(
        _fingerprint_value
    )
    _plan_fingerprint = field_validator("plan_fingerprint")(_fingerprint_value)
    _context_fingerprint = field_validator("context_fingerprint")(_fingerprint_value)
    _proposed_at = field_validator("proposed_at")(
        lambda value: _utc(value, field="proposed_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("evidence_trace", mode="before")
    @classmethod
    def validate_evidence_tuple(cls, value: object) -> object:
        return _tuple(value, field="evidence_trace")

    @model_validator(mode="after")
    def validate_proposal(self) -> FirmwareEngineeringProposal:
        evidence_ids = tuple(item.evidence_id for item in self.evidence_trace)
        if evidence_ids != tuple(sorted(evidence_ids)) or len(evidence_ids) != len(
            set(evidence_ids)
        ):
            raise ValueError("firmware evidence trace must be sorted and unique")
        if (
            self.review.proposal_id != self.proposal_id
            or self.review.hardware_proposal_fingerprint
            != self.hardware_proposal_fingerprint
            or self.review.requirement_fingerprint != self.requirement_fingerprint
            or self.review.context_fingerprint != self.context_fingerprint
            or self.execution_contract.build_proposal_fingerprint
            != self.build.fingerprint
            or self.execution_contract.debug_strategy_fingerprint
            != self.debug_strategy.fingerprint
            or self.execution_contract.proposal_id != self.proposal_id
            or self.execution_contract.hardware_proposal_fingerprint
            != self.hardware_proposal_fingerprint
            or self.execution_contract.requirement_fingerprint
            != self.requirement_fingerprint
            or self.execution_contract.context_fingerprint != self.context_fingerprint
        ):
            raise ValueError("firmware proposal binding mismatch")
        expected = firmware_engineering_proposal_fingerprint(
            proposal_id=self.proposal_id,
            project_id=self.project_id,
            hardware_proposal_fingerprint=self.hardware_proposal_fingerprint,
            requirement_fingerprint=self.requirement_fingerprint,
            plan_fingerprint=self.plan_fingerprint,
            context_fingerprint=self.context_fingerprint,
            platform=self.platform,
            architecture=self.architecture,
            driver_design=self.driver_design,
            task_architecture=self.task_architecture,
            interface_contracts=self.interface_contracts,
            code_generation=self.code_generation,
            build=self.build,
            debug_strategy=self.debug_strategy,
            execution_contract=self.execution_contract,
            evidence_trace=self.evidence_trace,
            review=self.review,
            proposed_at=self.proposed_at,
            candidate_semantics=self.candidate_semantics,
            review_required=self.review_required,
        )
        if self.fingerprint != expected:
            raise ValueError("firmware proposal fingerprint mismatch")
        return self
