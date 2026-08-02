"""Immutable contracts for the proposal-only Engineering Artifact Layer."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
_FINGERPRINT = re.compile(r"^sha256:[0-9a-f]{64}$")
_ABSOLUTE_PATH = re.compile(r"(?:^[A-Za-z]:[\\/]|^\\\\|^file://|^/)")
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|password|credential|secret)",
    re.IGNORECASE,
)


class _ArtifactContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        revalidate_instances="always",
        hide_input_in_errors=True,
    )


def _identifier(value: object, *, field: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    checked = unicodedata.normalize("NFC", value.strip())
    if _IDENTIFIER.fullmatch(checked) is None:
        raise ValueError(f"{field} is invalid")
    return checked


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _safe_text(value: object, *, field: str, maximum: int = 256) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    checked = unicodedata.normalize("NFC", value.strip())
    if not checked or len(checked) > maximum:
        raise ValueError(f"{field} is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in checked):
        raise ValueError(f"{field} is invalid")
    if _ABSOLUTE_PATH.search(checked) or _SENSITIVE.search(checked):
        raise ValueError(f"{field} is invalid")
    return checked


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


def _tokens(value: object, *, field: str) -> tuple[str, ...]:
    values = _tuple(value, field=field)
    checked = tuple(_token(item, field=field) for item in values)
    if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
        raise ValueError(f"{field} must be sorted and unique")
    return checked


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


def _fingerprint(kind: str, **values: object) -> str:
    encoded = json.dumps(
        _jsonable({"kind": kind, **values}),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class _Fingerprinted(_ArtifactContract):
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> _Fingerprinted:
        values = {
            name: getattr(self, name)
            for name in type(self).model_fields
            if name != "fingerprint"
        }
        if self.fingerprint != _fingerprint(type(self).__name__, **values):
            raise ValueError(f"{type(self).__name__} fingerprint mismatch")
        return self


def _model_fingerprint(model_type: type[_Fingerprinted], **values: object) -> str:
    return _fingerprint(model_type.__name__, **values)


class ArtifactType(StrEnum):
    FIRMWARE_STRUCTURE = "FIRMWARE_STRUCTURE"
    HARDWARE_MODEL = "HARDWARE_MODEL"
    SCHEMATIC_INTENT = "SCHEMATIC_INTENT"
    PCB_CONSTRAINT = "PCB_CONSTRAINT"


class ArtifactStatus(StrEnum):
    GENERATED = "GENERATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"


class ArtifactSourceType(StrEnum):
    REQUIREMENT = "REQUIREMENT"
    CONTEXT = "CONTEXT"
    HARDWARE_PROPOSAL = "HARDWARE_PROPOSAL"
    FIRMWARE_PROPOSAL = "FIRMWARE_PROPOSAL"


class FirmwareModuleGroup(StrEnum):
    BSP = "BSP"
    DRIVERS = "DRIVERS"
    MIDDLEWARE = "MIDDLEWARE"
    APPLICATION = "APPLICATION"
    TESTS = "TESTS"


class FirmwareModuleKind(StrEnum):
    ARCHITECTURE = "ARCHITECTURE"
    DRIVER = "DRIVER"
    INTENT = "INTENT"


class ConstraintCategory(StrEnum):
    FUNCTIONAL = "FUNCTIONAL"
    COMMUNICATION = "COMMUNICATION"
    POWER = "POWER"
    HARDWARE = "HARDWARE"


class ArtifactFindingCode(StrEnum):
    ARTIFACT_REVIEW_REQUIRED = "ARTIFACT_REVIEW_REQUIRED"
    SOURCE_GENERATION_UNAVAILABLE = "SOURCE_GENERATION_UNAVAILABLE"
    EDA_GENERATION_UNAVAILABLE = "EDA_GENERATION_UNAVAILABLE"
    HARDWARE_MODEL_UNRESOLVED = "HARDWARE_MODEL_UNRESOLVED"
    INTERFACE_DETAIL_UNRESOLVED = "INTERFACE_DETAIL_UNRESOLVED"
    FIRMWARE_IMPLEMENTATION_UNRESOLVED = "FIRMWARE_IMPLEMENTATION_UNRESOLVED"


class ArtifactReviewState(StrEnum):
    PENDING = "PENDING"


class ValidationAcquisitionStatus(StrEnum):
    COMPLETED = "COMPLETED"
    UNAVAILABLE = "UNAVAILABLE"


class FirmwareModuleArtifact(_Fingerprinted):
    module_reference: str
    module_group: FirmwareModuleGroup
    responsibility: str
    dependency_references: tuple[str, ...]
    unresolved: bool

    _module_reference = field_validator("module_reference")(
        lambda value: _identifier(value, field="module_reference")
    )
    _responsibility = field_validator("responsibility")(
        lambda value: _token(value, field="responsibility")
    )
    _dependencies = field_validator("dependency_references", mode="before")(
        lambda value: _identifiers(value, field="dependency_references")
    )


class CodeSkeletonProjection(_Fingerprinted):
    source_kind: FirmwareModuleKind
    module_reference: str
    module_group: FirmwareModuleGroup
    responsibility: str
    dependency_references: tuple[str, ...]
    unresolved: bool

    _module_reference = field_validator("module_reference")(
        lambda value: _identifier(value, field="module_reference")
    )
    _responsibility = field_validator("responsibility")(
        lambda value: _token(value, field="responsibility")
    )
    _dependencies = field_validator("dependency_references", mode="before")(
        lambda value: _identifiers(value, field="dependency_references")
    )


class FirmwareArtifactProjection(_Fingerprinted):
    candidate_semantics: Literal["unverified"] = "unverified"
    modules: tuple[FirmwareModuleArtifact, ...]
    code_skeletons: tuple[CodeSkeletonProjection, ...]

    @field_validator("modules", "code_skeletons", mode="before")
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_order(self) -> FirmwareArtifactProjection:
        if tuple(item.module_group for item in self.modules) != tuple(
            FirmwareModuleGroup
        ):
            raise ValueError("firmware modules are invalid")
        keys = tuple(
            (item.source_kind.value, item.module_reference)
            for item in self.code_skeletons
        )
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("code skeletons must be sorted and unique")
        return self


class UnifiedComponent(_Fingerprinted):
    component_id: str
    category: str
    reference: str
    evidence_ids: tuple[str, ...]
    unresolved: bool

    _component_id = field_validator("component_id")(
        lambda value: _identifier(value, field="component_id")
    )
    _category = field_validator("category")(
        lambda value: _token(value, field="category")
    )
    _reference = field_validator("reference")(
        lambda value: _safe_text(value, field="reference", maximum=128)
    )
    _evidence_ids = field_validator("evidence_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_ids")
    )


class UnifiedInterface(_Fingerprinted):
    interface_id: str
    protocol: str
    source_component: str | None = None
    target_component: str | None = None
    evidence_ids: tuple[str, ...]

    _interface_id = field_validator("interface_id")(
        lambda value: _identifier(value, field="interface_id")
    )
    _protocol = field_validator("protocol")(
        lambda value: _token(value, field="protocol")
    )
    _evidence_ids = field_validator("evidence_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_ids")
    )

    @field_validator("source_component", "target_component")
    @classmethod
    def validate_optional_component(cls, value: object, info) -> str | None:
        if value is None:
            return None
        return _identifier(value, field=info.field_name)


class UnifiedConstraint(_Fingerprinted):
    category: ConstraintCategory
    key: str
    value: str | None = None

    _key = field_validator("key")(lambda value: _token(value, field="key"))

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: object) -> str | None:
        if value is None:
            return None
        return _safe_text(value, field="value", maximum=128)


class UnifiedHardwareModel(_Fingerprinted):
    candidate_semantics: Literal["unverified"] = "unverified"
    components: tuple[UnifiedComponent, ...]
    interfaces: tuple[UnifiedInterface, ...]
    constraints: tuple[UnifiedConstraint, ...]

    @field_validator("components", "interfaces", "constraints", mode="before")
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_order(self) -> UnifiedHardwareModel:
        component_ids = tuple(item.component_id for item in self.components)
        interface_ids = tuple(item.interface_id for item in self.interfaces)
        order = {value: index for index, value in enumerate(ConstraintCategory)}
        constraint_keys = tuple(
            (order[item.category], item.key, item.value or "")
            for item in self.constraints
        )
        if component_ids != tuple(sorted(component_ids)) or len(component_ids) != len(
            set(component_ids)
        ):
            raise ValueError("components must be sorted and unique")
        if interface_ids != tuple(sorted(interface_ids)) or len(interface_ids) != len(
            set(interface_ids)
        ):
            raise ValueError("interfaces must be sorted and unique")
        if constraint_keys != tuple(sorted(constraint_keys)) or len(
            constraint_keys
        ) != len(set(constraint_keys)):
            raise ValueError("constraints must be sorted and unique")
        return self


class SchematicIntentArtifact(_Fingerprinted):
    candidate_semantics: Literal["unverified"] = "unverified"
    component_references: tuple[str, ...]
    interface_references: tuple[str, ...]
    power_requirement_references: tuple[str, ...]
    net_intents: tuple[str, ...] = ()

    _components = field_validator("component_references", mode="before")(
        lambda value: _identifiers(value, field="component_references")
    )
    _interfaces = field_validator("interface_references", mode="before")(
        lambda value: _identifiers(value, field="interface_references")
    )
    _power = field_validator("power_requirement_references", mode="before")(
        lambda value: _tokens(value, field="power_requirement_references")
    )

    @field_validator("net_intents", mode="before")
    @classmethod
    def validate_no_nets(cls, value: object) -> tuple[str, ...]:
        if _tuple(value, field="net_intents"):
            raise ValueError("net intents are unavailable")
        return ()


class PCBConstraintArtifactItem(_Fingerprinted):
    category: str
    subject_reference: str
    rule_code: str
    evidence_ids: tuple[str, ...]

    _category = field_validator("category")(
        lambda value: _token(value, field="category")
    )
    _subject = field_validator("subject_reference")(
        lambda value: _identifier(value, field="subject_reference")
    )
    _rule = field_validator("rule_code")(lambda value: _token(value, field="rule_code"))
    _evidence_ids = field_validator("evidence_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_ids")
    )


class PCBConstraintArtifact(_Fingerprinted):
    candidate_semantics: Literal["unverified"] = "unverified"
    constraints: tuple[PCBConstraintArtifactItem, ...]

    @field_validator("constraints", mode="before")
    @classmethod
    def validate_constraints(cls, value: object) -> object:
        return _tuple(value, field="constraints")

    @model_validator(mode="after")
    def validate_order(self) -> PCBConstraintArtifact:
        keys = tuple(
            (item.category, item.subject_reference, item.rule_code)
            for item in self.constraints
        )
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("PCB constraints must be sorted and unique")
        return self


class HardwareArtifactProjection(_Fingerprinted):
    candidate_semantics: Literal["unverified"] = "unverified"
    unified_model: UnifiedHardwareModel
    schematic_intent: SchematicIntentArtifact
    pcb_constraints: PCBConstraintArtifact


class ArtifactContractEntry(_Fingerprinted):
    artifact_type: ArtifactType
    status: ArtifactStatus
    artifact_fingerprint: str

    _artifact_fingerprint = field_validator("artifact_fingerprint")(_fingerprint_value)


class ArtifactSourceReference(_Fingerprinted):
    source_type: ArtifactSourceType
    source_fingerprint: str

    _source_fingerprint = field_validator("source_fingerprint")(_fingerprint_value)


class ArtifactSourceBinding(_Fingerprinted):
    artifact_type: ArtifactType
    sources: tuple[ArtifactSourceReference, ...]

    @field_validator("sources", mode="before")
    @classmethod
    def validate_sources_tuple(cls, value: object) -> object:
        return _tuple(value, field="sources")

    @model_validator(mode="after")
    def validate_order(self) -> ArtifactSourceBinding:
        order = {value: index for index, value in enumerate(ArtifactSourceType)}
        keys = tuple(order[item.source_type] for item in self.sources)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("artifact sources must be sorted and unique")
        return self


def artifact_source_fingerprint(
    *, source_bindings: tuple[ArtifactSourceBinding, ...]
) -> str:
    return _fingerprint("ArtifactSourceBindings", source_bindings=source_bindings)


class EngineeringArtifactContract(_Fingerprinted):
    candidate_semantics: Literal["unverified"] = "unverified"
    artifacts: tuple[ArtifactContractEntry, ...]
    source_bindings: tuple[ArtifactSourceBinding, ...]
    artifact_source_fingerprint: str
    review_required: Literal[True] = True

    _source_fingerprint = field_validator("artifact_source_fingerprint")(
        _fingerprint_value
    )

    @field_validator("artifacts", "source_bindings", mode="before")
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_contract(self) -> EngineeringArtifactContract:
        if tuple(item.artifact_type for item in self.artifacts) != tuple(ArtifactType):
            raise ValueError("artifact entries are invalid")
        if tuple(item.artifact_type for item in self.source_bindings) != tuple(
            ArtifactType
        ):
            raise ValueError("artifact source bindings are invalid")
        if self.artifact_source_fingerprint != artifact_source_fingerprint(
            source_bindings=self.source_bindings
        ):
            raise ValueError("artifact source fingerprint mismatch")
        return self


class ArtifactReviewProjection(_Fingerprinted):
    proposal_id: str
    hardware_proposal_fingerprint: str
    firmware_proposal_fingerprint: str
    requirement_fingerprint: str
    context_fingerprint: str
    validation_report_fingerprint: str | None = None
    validation_acquisition_status: ValidationAcquisitionStatus | None = None
    validation_coverage_count: int = Field(ge=0)
    validation_finding_codes: tuple[str, ...]
    artifact_count: int = Field(ge=0, le=4)
    unresolved_count: int = Field(ge=0, le=4)
    finding_codes: tuple[ArtifactFindingCode, ...]
    review_state: Literal[ArtifactReviewState.PENDING] = ArtifactReviewState.PENDING
    review_required: Literal[True] = True

    _proposal_id = field_validator("proposal_id")(
        lambda value: _identifier(value, field="proposal_id")
    )
    _hardware_fingerprint = field_validator("hardware_proposal_fingerprint")(
        _fingerprint_value
    )
    _firmware_fingerprint = field_validator("firmware_proposal_fingerprint")(
        _fingerprint_value
    )
    _requirement_fingerprint = field_validator("requirement_fingerprint")(
        _fingerprint_value
    )
    _context_fingerprint = field_validator("context_fingerprint")(_fingerprint_value)

    @field_validator("validation_report_fingerprint")
    @classmethod
    def validate_optional_fingerprint(cls, value: object) -> str | None:
        if value is None:
            return None
        return _fingerprint_value(value)

    _validation_codes = field_validator("validation_finding_codes", mode="before")(
        lambda value: _tokens(value, field="validation_finding_codes")
    )

    @field_validator("finding_codes", mode="before")
    @classmethod
    def validate_finding_tuple(cls, value: object) -> object:
        return _tuple(value, field="finding_codes")

    @model_validator(mode="after")
    def validate_review(self) -> ArtifactReviewProjection:
        if self.finding_codes != tuple(ArtifactFindingCode):
            raise ValueError("artifact findings are invalid")
        if (self.validation_report_fingerprint is None) != (
            self.validation_acquisition_status is None
        ):
            raise ValueError("validation review binding is invalid")
        if self.validation_report_fingerprint is None and (
            self.validation_coverage_count or self.validation_finding_codes
        ):
            raise ValueError("validation review data requires a report")
        return self


def engineering_generation_report_fingerprint(**values: object) -> str:
    values.pop("schema_version", None)
    return _fingerprint("EngineeringGenerationReport", **values)


class EngineeringGenerationReport(_ArtifactContract):
    schema_version: Literal["1.0"] = "1.0"
    proposal_id: str
    project_id: str
    requirement_fingerprint: str
    plan_fingerprint: str
    context_fingerprint: str
    hardware_proposal_fingerprint: str
    firmware_proposal_fingerprint: str
    validation_report_fingerprint: str | None = None
    firmware_artifact: FirmwareArtifactProjection
    hardware_artifact: HardwareArtifactProjection
    unified_hardware_model: UnifiedHardwareModel
    review: ArtifactReviewProjection
    artifact_contract: EngineeringArtifactContract
    proposed_at: datetime
    candidate_semantics: Literal["unverified"] = "unverified"
    review_required: Literal[True] = True
    fingerprint: str

    @field_validator("proposal_id", "project_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _requirement_fingerprint = field_validator("requirement_fingerprint")(
        _fingerprint_value
    )
    _plan_fingerprint = field_validator("plan_fingerprint")(_fingerprint_value)
    _context_fingerprint = field_validator("context_fingerprint")(_fingerprint_value)
    _hardware_fingerprint = field_validator("hardware_proposal_fingerprint")(
        _fingerprint_value
    )
    _firmware_fingerprint = field_validator("firmware_proposal_fingerprint")(
        _fingerprint_value
    )
    _proposed_at = field_validator("proposed_at")(
        lambda value: _utc(value, field="proposed_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("validation_report_fingerprint")
    @classmethod
    def validate_optional_fingerprint(cls, value: object) -> str | None:
        if value is None:
            return None
        return _fingerprint_value(value)

    @model_validator(mode="after")
    def validate_report(self) -> EngineeringGenerationReport:
        if self.unified_hardware_model != self.hardware_artifact.unified_model:
            raise ValueError("unified hardware model binding mismatch")
        if (
            self.review.proposal_id != self.proposal_id
            or self.review.requirement_fingerprint != self.requirement_fingerprint
            or self.review.context_fingerprint != self.context_fingerprint
            or self.review.hardware_proposal_fingerprint
            != self.hardware_proposal_fingerprint
            or self.review.firmware_proposal_fingerprint
            != self.firmware_proposal_fingerprint
            or self.review.validation_report_fingerprint
            != self.validation_report_fingerprint
        ):
            raise ValueError("artifact review binding mismatch")
        expected = engineering_generation_report_fingerprint(
            proposal_id=self.proposal_id,
            project_id=self.project_id,
            requirement_fingerprint=self.requirement_fingerprint,
            plan_fingerprint=self.plan_fingerprint,
            context_fingerprint=self.context_fingerprint,
            hardware_proposal_fingerprint=self.hardware_proposal_fingerprint,
            firmware_proposal_fingerprint=self.firmware_proposal_fingerprint,
            validation_report_fingerprint=self.validation_report_fingerprint,
            firmware_artifact=self.firmware_artifact,
            hardware_artifact=self.hardware_artifact,
            unified_hardware_model=self.unified_hardware_model,
            review=self.review,
            artifact_contract=self.artifact_contract,
            proposed_at=self.proposed_at,
            candidate_semantics=self.candidate_semantics,
            review_required=self.review_required,
        )
        if self.fingerprint != expected:
            raise ValueError("engineering generation report fingerprint mismatch")
        return self
