"""Immutable, content-minimized Hardware Validation contracts."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_METRIC = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_FINGERPRINT = re.compile(r"^sha256:[0-9a-f]{64}$")


class _ValidationContract(BaseModel):
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


class ValidationTestType(StrEnum):
    CAMERA_CAPTURE = "CAMERA_CAPTURE"
    NETWORK_CONNECTIVITY = "NETWORK_CONNECTIVITY"
    STORAGE_OPERATION = "STORAGE_OPERATION"
    POWER_OBSERVATION = "POWER_OBSERVATION"
    FIRMWARE_BUILD = "FIRMWARE_BUILD"


class EvidenceType(StrEnum):
    UART_LOG = "UART_LOG"
    POWER_MEASUREMENT = "POWER_MEASUREMENT"
    NETWORK_METRIC = "NETWORK_METRIC"
    TEMPERATURE = "TEMPERATURE"
    FPS_RESULT = "FPS_RESULT"
    MEMORY_STAT = "MEMORY_STAT"


class EvidenceSourceType(StrEnum):
    CALLER_PROVIDED = "CALLER_PROVIDED"
    DEBUG_RUNTIME = "DEBUG_RUNTIME"
    TELEMETRY_RUNTIME = "TELEMETRY_RUNTIME"
    HIL_ADAPTER = "HIL_ADAPTER"
    DEVICE_ADAPTER = "DEVICE_ADAPTER"
    MOCK = "MOCK"


class EvidenceQualification(StrEnum):
    VERIFIED = "VERIFIED"
    CANDIDATE = "CANDIDATE"


class EvidenceOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class EvidenceMetricUnit(StrEnum):
    COUNT = "count"
    PERCENT = "percent"
    BYTES = "bytes"
    MILLISECONDS = "milliseconds"
    CELSIUS = "celsius"
    VOLTS = "volts"
    AMPERES = "amperes"
    MILLIAMPERES = "milliamperes"
    HERTZ = "hertz"
    FRAMES_PER_SECOND = "frames_per_second"


class ValidationAnalysisStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    NOT_MET = "NOT_MET"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


class ProjectionState(StrEnum):
    UNKNOWN = "UNKNOWN"


class AcquisitionStatus(StrEnum):
    COMPLETED = "COMPLETED"
    UNAVAILABLE = "UNAVAILABLE"


class ValidationFindingCode(StrEnum):
    TEST_NOT_EXECUTED = "TEST_NOT_EXECUTED"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    REQUIREMENT_NOT_MET = "REQUIREMENT_NOT_MET"
    MEASUREMENT_CONFLICT = "MEASUREMENT_CONFLICT"
    EVIDENCE_BASELINE_CONFLICT = "EVIDENCE_BASELINE_CONFLICT"
    HARDWARE_STATE_UNKNOWN = "HARDWARE_STATE_UNKNOWN"
    FIRMWARE_STATE_UNKNOWN = "FIRMWARE_STATE_UNKNOWN"
    VALIDATION_UNAVAILABLE = "VALIDATION_UNAVAILABLE"


class ValidationFindingSeverity(StrEnum):
    REVIEW = "REVIEW"
    BLOCKING = "BLOCKING"


def evidence_safe_metadata_fingerprint(**values: object) -> str:
    metric_value = values.get("metric_value")
    if type(metric_value) is float and not math.isfinite(metric_value):
        return "sha256:" + "0" * 64
    return _fingerprint("EvidenceSafeMetadata", **values)


class EvidenceSafeMetadata(_ValidationContract):
    test_type: ValidationTestType
    outcome: EvidenceOutcome
    observation_code: str
    metric_name: str | None = None
    metric_value: int | float | None = None
    metric_unit: EvidenceMetricUnit | None = None
    sample_count: int = Field(ge=1, le=1_000_000)
    reference_ids: tuple[str, ...]
    observed_at: datetime
    fingerprint: str

    _observation_code = field_validator("observation_code")(
        lambda value: _token(value, field="observation_code")
    )
    _reference_ids = field_validator("reference_ids", mode="before")(
        lambda value: _identifiers(value, field="reference_ids")
    )
    _observed_at = field_validator("observed_at")(
        lambda value: _utc(value, field="observed_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("metric_name")
    @classmethod
    def validate_metric_name(cls, value: object) -> str | None:
        if value is None:
            return None
        if type(value) is not str or _METRIC.fullmatch(value) is None:
            raise ValueError("metric_name is invalid")
        return value

    @field_validator("metric_value")
    @classmethod
    def validate_metric_value(cls, value: object) -> int | float | None:
        if value is None:
            return None
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("metric_value must be finite and non-boolean")
        return value

    @model_validator(mode="after")
    def validate_projection(self) -> EvidenceSafeMetadata:
        metric_fields = (self.metric_name, self.metric_value, self.metric_unit)
        if any(item is None for item in metric_fields) and any(
            item is not None for item in metric_fields
        ):
            raise ValueError("metric fields must be supplied together")
        expected = evidence_safe_metadata_fingerprint(
            test_type=self.test_type,
            outcome=self.outcome,
            observation_code=self.observation_code,
            metric_name=self.metric_name,
            metric_value=self.metric_value,
            metric_unit=self.metric_unit,
            sample_count=self.sample_count,
            reference_ids=self.reference_ids,
            observed_at=self.observed_at,
        )
        if self.fingerprint != expected:
            raise ValueError("evidence metadata fingerprint mismatch")
        return self


def evidence_record_fingerprint(**values: object) -> str:
    return _fingerprint("EvidenceRecord", **values)


class EvidenceRecord(_ValidationContract):
    evidence_id: str
    evidence_type: EvidenceType
    source_type: EvidenceSourceType
    qualification: EvidenceQualification
    safe_metadata: EvidenceSafeMetadata
    fingerprint: str

    _evidence_id = field_validator("evidence_id")(
        lambda value: _identifier(value, field="evidence_id")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_record(self) -> EvidenceRecord:
        measurement_types = {
            EvidenceType.POWER_MEASUREMENT,
            EvidenceType.NETWORK_METRIC,
            EvidenceType.TEMPERATURE,
            EvidenceType.FPS_RESULT,
            EvidenceType.MEMORY_STAT,
        }
        if (
            self.evidence_type in measurement_types
            and self.safe_metadata.metric_name is None
        ):
            raise ValueError("measurement evidence requires a metric")
        expected = evidence_record_fingerprint(
            evidence_id=self.evidence_id,
            evidence_type=self.evidence_type,
            source_type=self.source_type,
            qualification=self.qualification,
            safe_metadata=self.safe_metadata,
        )
        if self.fingerprint != expected:
            raise ValueError("evidence record fingerprint mismatch")
        return self


def evidence_snapshot_fingerprint(**values: object) -> str:
    values.pop("schema_version", None)
    return _fingerprint("EvidenceSnapshot", **values)


class EvidenceSnapshot(_ValidationContract):
    schema_version: Literal["1.0"] = "1.0"
    snapshot_id: str
    project_id: str
    requirement_fingerprint: str
    hardware_proposal_fingerprint: str
    firmware_proposal_fingerprint: str
    context_fingerprint: str
    records: tuple[EvidenceRecord, ...]
    captured_at: datetime
    fingerprint: str

    @field_validator("snapshot_id", "project_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _requirement_fingerprint = field_validator("requirement_fingerprint")(
        _fingerprint_value
    )
    _hardware_fingerprint = field_validator("hardware_proposal_fingerprint")(
        _fingerprint_value
    )
    _firmware_fingerprint = field_validator("firmware_proposal_fingerprint")(
        _fingerprint_value
    )
    _context_fingerprint = field_validator("context_fingerprint")(_fingerprint_value)
    _captured_at = field_validator("captured_at")(
        lambda value: _utc(value, field="captured_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("records", mode="before")
    @classmethod
    def validate_records_tuple(cls, value: object) -> object:
        return _tuple(value, field="records")

    @model_validator(mode="after")
    def validate_snapshot(self) -> EvidenceSnapshot:
        ids = tuple(item.evidence_id for item in self.records)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("evidence records must be sorted and unique")
        expected = evidence_snapshot_fingerprint(
            snapshot_id=self.snapshot_id,
            project_id=self.project_id,
            requirement_fingerprint=self.requirement_fingerprint,
            hardware_proposal_fingerprint=self.hardware_proposal_fingerprint,
            firmware_proposal_fingerprint=self.firmware_proposal_fingerprint,
            context_fingerprint=self.context_fingerprint,
            records=self.records,
            captured_at=self.captured_at,
        )
        if self.fingerprint != expected:
            raise ValueError("evidence snapshot fingerprint mismatch")
        return self


def validation_test_plan_item_fingerprint(**values: object) -> str:
    return _fingerprint("ValidationTestPlanItem", **values)


class ValidationTestPlanItem(_ValidationContract):
    test_type: ValidationTestType
    objective_code: str
    target_references: tuple[str, ...]
    required_evidence_types: tuple[EvidenceType, ...]
    execution_state: Literal["NOT_EXECUTED"] = "NOT_EXECUTED"
    fingerprint: str

    _objective_code = field_validator("objective_code")(
        lambda value: _token(value, field="objective_code")
    )
    _target_references = field_validator("target_references", mode="before")(
        lambda value: _identifiers(value, field="target_references")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("required_evidence_types", mode="before")
    @classmethod
    def validate_evidence_types(cls, value: object) -> object:
        return _tuple(value, field="required_evidence_types")

    @model_validator(mode="after")
    def validate_item(self) -> ValidationTestPlanItem:
        if not self.required_evidence_types or len(self.required_evidence_types) != len(
            set(self.required_evidence_types)
        ):
            raise ValueError("required evidence types are invalid")
        expected = validation_test_plan_item_fingerprint(
            test_type=self.test_type,
            objective_code=self.objective_code,
            target_references=self.target_references,
            required_evidence_types=self.required_evidence_types,
            execution_state=self.execution_state,
        )
        if self.fingerprint != expected:
            raise ValueError("test plan item fingerprint mismatch")
        return self


def test_plan_proposal_fingerprint(**values: object) -> str:
    return _fingerprint("TestPlanProposal", **values)


class TestPlanProposal(_ValidationContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    tests: tuple[ValidationTestPlanItem, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("tests", mode="before")
    @classmethod
    def validate_tests_tuple(cls, value: object) -> object:
        return _tuple(value, field="tests")

    @model_validator(mode="after")
    def validate_plan(self) -> TestPlanProposal:
        order = {value: index for index, value in enumerate(ValidationTestType)}
        keys = tuple(order[item.test_type] for item in self.tests)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("validation tests must be sorted and unique")
        if self.fingerprint != test_plan_proposal_fingerprint(tests=self.tests):
            raise ValueError("test plan fingerprint mismatch")
        return self


def device_evidence_collection_request_fingerprint(**values: object) -> str:
    return _fingerprint("DeviceEvidenceCollectionRequest", **values)


class DeviceEvidenceCollectionRequest(_ValidationContract):
    proposal_id: str
    project_id: str
    requirement_fingerprint: str
    hardware_proposal_fingerprint: str
    firmware_proposal_fingerprint: str
    context_fingerprint: str
    baseline_evidence_fingerprint: str
    test_plan: TestPlanProposal
    requested_at: datetime
    fingerprint: str

    @field_validator("proposal_id", "project_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _requirement_fingerprint = field_validator("requirement_fingerprint")(
        _fingerprint_value
    )
    _hardware_fingerprint = field_validator("hardware_proposal_fingerprint")(
        _fingerprint_value
    )
    _firmware_fingerprint = field_validator("firmware_proposal_fingerprint")(
        _fingerprint_value
    )
    _context_fingerprint = field_validator("context_fingerprint")(_fingerprint_value)
    _baseline_fingerprint = field_validator("baseline_evidence_fingerprint")(
        _fingerprint_value
    )
    _requested_at = field_validator("requested_at")(
        lambda value: _utc(value, field="requested_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_request(self) -> DeviceEvidenceCollectionRequest:
        expected = device_evidence_collection_request_fingerprint(
            proposal_id=self.proposal_id,
            project_id=self.project_id,
            requirement_fingerprint=self.requirement_fingerprint,
            hardware_proposal_fingerprint=self.hardware_proposal_fingerprint,
            firmware_proposal_fingerprint=self.firmware_proposal_fingerprint,
            context_fingerprint=self.context_fingerprint,
            baseline_evidence_fingerprint=self.baseline_evidence_fingerprint,
            test_plan=self.test_plan,
            requested_at=self.requested_at,
        )
        if self.fingerprint != expected:
            raise ValueError("collection request fingerprint mismatch")
        return self


def device_evidence_collection_result_fingerprint(**values: object) -> str:
    return _fingerprint("DeviceEvidenceCollectionResult", **values)


class DeviceEvidenceCollectionResult(_ValidationContract):
    proposal_id: str
    project_id: str
    test_plan_fingerprint: str
    records: tuple[EvidenceRecord, ...]
    collected_at: datetime
    fingerprint: str

    @field_validator("proposal_id", "project_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _plan_fingerprint = field_validator("test_plan_fingerprint")(_fingerprint_value)
    _collected_at = field_validator("collected_at")(
        lambda value: _utc(value, field="collected_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("records", mode="before")
    @classmethod
    def validate_records_tuple(cls, value: object) -> object:
        return _tuple(value, field="records")

    @model_validator(mode="after")
    def validate_result(self) -> DeviceEvidenceCollectionResult:
        ids = tuple(item.evidence_id for item in self.records)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("collection records must be sorted and unique")
        expected = device_evidence_collection_result_fingerprint(
            proposal_id=self.proposal_id,
            project_id=self.project_id,
            test_plan_fingerprint=self.test_plan_fingerprint,
            records=self.records,
            collected_at=self.collected_at,
        )
        if self.fingerprint != expected:
            raise ValueError("collection result fingerprint mismatch")
        return self


class EvidenceAnalysisResult(_ValidationContract):
    test_type: ValidationTestType
    status: ValidationAnalysisStatus
    evidence_ids: tuple[str, ...]
    evidence_count: int = Field(ge=0)
    fingerprint: str

    _evidence_ids = field_validator("evidence_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_ids")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_result(self) -> EvidenceAnalysisResult:
        if self.evidence_count != len(self.evidence_ids):
            raise ValueError("analysis evidence count mismatch")
        expected = _fingerprint(
            "EvidenceAnalysisResult",
            test_type=self.test_type,
            status=self.status,
            evidence_ids=self.evidence_ids,
            evidence_count=self.evidence_count,
        )
        if self.fingerprint != expected:
            raise ValueError("analysis result fingerprint mismatch")
        return self


class EvidenceAnalysisProjection(_ValidationContract):
    results: tuple[EvidenceAnalysisResult, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("results", mode="before")
    @classmethod
    def validate_results_tuple(cls, value: object) -> object:
        return _tuple(value, field="results")

    @model_validator(mode="after")
    def validate_projection(self) -> EvidenceAnalysisProjection:
        order = {value: index for index, value in enumerate(ValidationTestType)}
        keys = tuple(order[item.test_type] for item in self.results)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("analysis results must be sorted and unique")
        if self.fingerprint != _fingerprint(
            "EvidenceAnalysisProjection", results=self.results
        ):
            raise ValueError("analysis projection fingerprint mismatch")
        return self


class HILValidationItem(_ValidationContract):
    test_type: ValidationTestType
    expected_behavior_code: str
    required_evidence_types: tuple[EvidenceType, ...]
    state: Literal[ProjectionState.UNKNOWN] = ProjectionState.UNKNOWN

    _expected_behavior = field_validator("expected_behavior_code")(
        lambda value: _token(value, field="expected_behavior_code")
    )

    @field_validator("required_evidence_types", mode="before")
    @classmethod
    def validate_types_tuple(cls, value: object) -> object:
        return _tuple(value, field="required_evidence_types")


class HILValidationProjection(_ValidationContract):
    tests: tuple[HILValidationItem, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("tests", mode="before")
    @classmethod
    def validate_tests_tuple(cls, value: object) -> object:
        return _tuple(value, field="tests")

    @model_validator(mode="after")
    def validate_projection(self) -> HILValidationProjection:
        if self.fingerprint != _fingerprint(
            "HILValidationProjection", tests=self.tests
        ):
            raise ValueError("HIL projection fingerprint mismatch")
        return self


class DigitalTwinComponentState(_ValidationContract):
    component_reference: str
    expected_behavior_codes: tuple[str, ...]
    state: Literal[ProjectionState.UNKNOWN] = ProjectionState.UNKNOWN

    _component_reference = field_validator("component_reference")(
        lambda value: _identifier(value, field="component_reference")
    )

    @field_validator("expected_behavior_codes", mode="before")
    @classmethod
    def validate_codes(cls, value: object) -> tuple[str, ...]:
        values = _tuple(value, field="expected_behavior_codes")
        checked = tuple(_token(item, field="expected_behavior_code") for item in values)
        if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
            raise ValueError("expected behavior codes must be sorted and unique")
        return checked


class DigitalTwinStateProjection(_ValidationContract):
    components: tuple[DigitalTwinComponentState, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("components", mode="before")
    @classmethod
    def validate_components_tuple(cls, value: object) -> object:
        return _tuple(value, field="components")

    @model_validator(mode="after")
    def validate_projection(self) -> DigitalTwinStateProjection:
        keys = tuple(item.component_reference for item in self.components)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("digital twin components must be sorted and unique")
        if self.fingerprint != _fingerprint(
            "DigitalTwinStateProjection", components=self.components
        ):
            raise ValueError("digital twin fingerprint mismatch")
        return self


class ValidationEvidenceTrace(_ValidationContract):
    evidence_id: str
    evidence_type: EvidenceType
    source_type: EvidenceSourceType
    reference_ids: tuple[str, ...]
    record_fingerprint: str

    _evidence_id = field_validator("evidence_id")(
        lambda value: _identifier(value, field="evidence_id")
    )
    _reference_ids = field_validator("reference_ids", mode="before")(
        lambda value: _identifiers(value, field="reference_ids")
    )
    _record_fingerprint = field_validator("record_fingerprint")(_fingerprint_value)


class ValidationReviewFinding(_ValidationContract):
    code: ValidationFindingCode
    severity: ValidationFindingSeverity


class ValidationReviewProjection(_ValidationContract):
    proposal_id: str
    hardware_proposal_fingerprint: str
    firmware_proposal_fingerprint: str
    requirement_fingerprint: str
    context_fingerprint: str
    test_count: int = Field(ge=0)
    verified_evidence_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    coverage_count: int = Field(ge=0)
    findings: tuple[ValidationReviewFinding, ...]
    finding_codes: tuple[ValidationFindingCode, ...]
    review_required: Literal[True] = True
    fingerprint: str

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
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("findings", "finding_codes", mode="before")
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_review(self) -> ValidationReviewProjection:
        codes = tuple(item.code for item in self.findings)
        if codes != self.finding_codes or len(codes) != len(set(codes)):
            raise ValueError("review finding binding mismatch")
        expected = _fingerprint(
            "ValidationReviewProjection",
            proposal_id=self.proposal_id,
            hardware_proposal_fingerprint=self.hardware_proposal_fingerprint,
            firmware_proposal_fingerprint=self.firmware_proposal_fingerprint,
            requirement_fingerprint=self.requirement_fingerprint,
            context_fingerprint=self.context_fingerprint,
            test_count=self.test_count,
            verified_evidence_count=self.verified_evidence_count,
            candidate_count=self.candidate_count,
            coverage_count=self.coverage_count,
            findings=self.findings,
            finding_codes=self.finding_codes,
            review_required=self.review_required,
        )
        if self.fingerprint != expected:
            raise ValueError("validation review fingerprint mismatch")
        return self


def hardware_validation_report_fingerprint(**values: object) -> str:
    values.pop("schema_version", None)
    return _fingerprint("HardwareValidationReport", **values)


class HardwareValidationReport(_ValidationContract):
    schema_version: Literal["1.0"] = "1.0"
    proposal_id: str
    project_id: str
    hardware_proposal_fingerprint: str
    firmware_proposal_fingerprint: str
    requirement_fingerprint: str
    plan_fingerprint: str
    context_fingerprint: str
    baseline_evidence_fingerprint: str
    acquisition_status: AcquisitionStatus
    test_plan: TestPlanProposal
    evidence_analysis: EvidenceAnalysisProjection
    hil: HILValidationProjection
    digital_twin: DigitalTwinStateProjection
    evidence_trace: tuple[ValidationEvidenceTrace, ...]
    review: ValidationReviewProjection
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
    _firmware_fingerprint = field_validator("firmware_proposal_fingerprint")(
        _fingerprint_value
    )
    _requirement_fingerprint = field_validator("requirement_fingerprint")(
        _fingerprint_value
    )
    _plan_fingerprint = field_validator("plan_fingerprint")(_fingerprint_value)
    _context_fingerprint = field_validator("context_fingerprint")(_fingerprint_value)
    _baseline_fingerprint = field_validator("baseline_evidence_fingerprint")(
        _fingerprint_value
    )
    _proposed_at = field_validator("proposed_at")(
        lambda value: _utc(value, field="proposed_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("evidence_trace", mode="before")
    @classmethod
    def validate_trace_tuple(cls, value: object) -> object:
        return _tuple(value, field="evidence_trace")

    @model_validator(mode="after")
    def validate_report(self) -> HardwareValidationReport:
        ids = tuple(item.evidence_id for item in self.evidence_trace)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("evidence trace must be sorted and unique")
        if (
            self.review.proposal_id != self.proposal_id
            or self.review.hardware_proposal_fingerprint
            != self.hardware_proposal_fingerprint
            or self.review.firmware_proposal_fingerprint
            != self.firmware_proposal_fingerprint
            or self.review.requirement_fingerprint != self.requirement_fingerprint
            or self.review.context_fingerprint != self.context_fingerprint
        ):
            raise ValueError("validation report binding mismatch")
        expected = hardware_validation_report_fingerprint(
            proposal_id=self.proposal_id,
            project_id=self.project_id,
            hardware_proposal_fingerprint=self.hardware_proposal_fingerprint,
            firmware_proposal_fingerprint=self.firmware_proposal_fingerprint,
            requirement_fingerprint=self.requirement_fingerprint,
            plan_fingerprint=self.plan_fingerprint,
            context_fingerprint=self.context_fingerprint,
            baseline_evidence_fingerprint=self.baseline_evidence_fingerprint,
            acquisition_status=self.acquisition_status,
            test_plan=self.test_plan,
            evidence_analysis=self.evidence_analysis,
            hil=self.hil,
            digital_twin=self.digital_twin,
            evidence_trace=self.evidence_trace,
            review=self.review,
            proposed_at=self.proposed_at,
            candidate_semantics=self.candidate_semantics,
            review_required=self.review_required,
        )
        if self.fingerprint != expected:
            raise ValueError("hardware validation report fingerprint mismatch")
        return self
