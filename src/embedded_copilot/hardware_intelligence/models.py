"""Immutable contracts for simulation-first hardware intelligence."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$"
_TYPE_TOKEN = r"^[A-Z][A-Z0-9_]{2,63}$"
_METADATA_KEY = r"^[a-z][a-z0-9_]{0,63}$"
_METRIC_NAME = r"^[a-z][a-z0-9_]{0,63}$"
_FINGERPRINT = r"^sha256:[a-f0-9]{64}$"
_SENSITIVE = (
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|password\s*[:=]|credential\s*[:=]|secret\s*[:=])"
)
_ABSOLUTE_PATH = r"(?:^[A-Za-z]:[\\/]|^\\\\|^file://|^/)"


class _HardwareContract(BaseModel):
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
    candidate = unicodedata.normalize("NFC", value.strip())
    if re.fullmatch(_IDENTIFIER, candidate) is None:
        raise ValueError(f"{field} is invalid")
    return candidate


def _type_token(value: object, *, field: str) -> str:
    if type(value) is not str or re.fullmatch(_TYPE_TOKEN, value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _metadata_key(value: object) -> str:
    if type(value) is not str or re.fullmatch(_METADATA_KEY, value) is None:
        raise ValueError("metadata key is invalid")
    return value


def _safe_text(value: object, *, field: str, maximum: int = 1024) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if (
        not candidate
        or len(candidate) > maximum
        or any(character in candidate for character in ("\r", "\n", "\x00"))
        or re.search(_SENSITIVE, candidate, re.IGNORECASE) is not None
        or re.search(_ABSOLUTE_PATH, candidate) is not None
    ):
        raise ValueError(f"{field} is unsafe")
    return candidate


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


def _checked_fingerprint(value: object) -> str:
    if type(value) is not str or re.fullmatch(_FINGERPRINT, value) is None:
        raise ValueError("fingerprint is invalid")
    return value


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class HardwareMetricUnit(StrEnum):
    COUNT = "count"
    PERCENT = "percent"
    CELSIUS = "celsius"
    VOLTS = "volts"
    AMPERES = "amperes"
    HERTZ = "hertz"
    RPM = "rpm"


class HILProjectionStatus(StrEnum):
    OBSERVED = "OBSERVED"
    UNAVAILABLE = "UNAVAILABLE"


class HardwareValidationStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"


class HardwareValidationType(StrEnum):
    CONTRACT = "CONTRACT"
    SCHEMA = "SCHEMA"
    SIMULATION = "SIMULATION"
    THRESHOLD = "THRESHOLD"


class HardwareValidationDecision(StrEnum):
    APPROVED = "APPROVED"
    DENIED = "DENIED"


class HardwareIntelligenceState(StrEnum):
    CREATED = "CREATED"
    CONTEXT_READY = "CONTEXT_READY"
    TWIN_READY = "TWIN_READY"
    OBSERVATION_READY = "OBSERVATION_READY"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    FAILED = "FAILED"
    INVALID = "INVALID"


class HardwareProgressEventType(StrEnum):
    ANALYSIS_CREATED = "ANALYSIS_CREATED"
    CONTEXT_PROJECTED = "CONTEXT_PROJECTED"
    TWIN_PROJECTED = "TWIN_PROJECTED"
    OBSERVATION_PROJECTED = "OBSERVATION_PROJECTED"
    VALIDATION_STARTED = "VALIDATION_STARTED"
    VALIDATION_COMPLETED = "VALIDATION_COMPLETED"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    ANALYSIS_INVALID = "ANALYSIS_INVALID"


class HardwareFailureCode(StrEnum):
    TWIN_UNAVAILABLE = "twin_unavailable"
    TWIN_REJECTED = "twin_rejected"
    TELEMETRY_UNAVAILABLE = "telemetry_unavailable"
    OBSERVATION_REJECTED = "observation_rejected"
    VALIDATION_UNAVAILABLE = "validation_unavailable"
    VALIDATION_INVALID = "validation_invalid"
    APPROVAL_DENIED = "approval_denied"


class HardwareMetadata(_HardwareContract):
    key: str
    value: str

    _key = field_validator("key")(_metadata_key)
    _value = field_validator("value")(
        lambda value: _identifier(value, field="metadata value")
    )


def hardware_context_fingerprint(
    *,
    hardware_id: str,
    device_type: str,
    board_reference: str,
    safe_metadata: tuple[HardwareMetadata, ...],
) -> str:
    return _fingerprint(
        {
            "board_reference": board_reference,
            "device_type": device_type,
            "hardware_id": hardware_id,
            "safe_metadata": [item.model_dump(mode="json") for item in safe_metadata],
        }
    )


class HardwareContextProjection(_HardwareContract):
    hardware_id: str
    device_type: str
    board_reference: str
    safe_metadata: tuple[HardwareMetadata, ...]
    fingerprint: str

    _hardware_id = field_validator("hardware_id")(
        lambda value: _identifier(value, field="hardware_id")
    )
    _device_type = field_validator("device_type")(
        lambda value: _type_token(value, field="device_type")
    )
    _board_reference = field_validator("board_reference")(
        lambda value: _identifier(value, field="board_reference")
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("safe_metadata", mode="before")
    @classmethod
    def _metadata_tuple(cls, value: object) -> object:
        return _tuple(value, field="safe_metadata")

    @model_validator(mode="after")
    def _metadata_and_fingerprint(self) -> HardwareContextProjection:
        keys = tuple(item.key for item in self.safe_metadata)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("safe_metadata must be sorted and unique")
        if self.fingerprint != hardware_context_fingerprint(
            hardware_id=self.hardware_id,
            device_type=self.device_type,
            board_reference=self.board_reference,
            safe_metadata=self.safe_metadata,
        ):
            raise ValueError("context fingerprint mismatch")
        return self


class HardwareAnalysisRequest(_HardwareContract):
    hardware_id: str
    scenario_id: str
    context: HardwareContextProjection
    timestamp: datetime

    _hardware_id = field_validator("hardware_id")(
        lambda value: _identifier(value, field="hardware_id")
    )
    _scenario_id = field_validator("scenario_id")(
        lambda value: _identifier(value, field="scenario_id")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )

    @model_validator(mode="after")
    def _context_binding(self) -> HardwareAnalysisRequest:
        if self.hardware_id != self.context.hardware_id:
            raise ValueError("hardware request binding mismatch")
        return self


class DigitalTwinRequest(_HardwareContract):
    hardware_id: str
    scenario_id: str
    context: HardwareContextProjection
    timestamp: datetime

    _hardware_id = field_validator("hardware_id")(
        lambda value: _identifier(value, field="hardware_id")
    )
    _scenario_id = field_validator("scenario_id")(
        lambda value: _identifier(value, field="scenario_id")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )


class DigitalTwinMetric(_HardwareContract):
    metric_name: str
    value: int | float
    unit: HardwareMetricUnit

    @field_validator("metric_name")
    @classmethod
    def _metric_name(cls, value: str) -> str:
        if type(value) is not str or re.fullmatch(_METRIC_NAME, value) is None:
            raise ValueError("metric_name is invalid")
        return value

    @field_validator("value")
    @classmethod
    def _metric_value(cls, value: int | float) -> int | float:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("metric value is invalid")
        return value


def digital_twin_fingerprint(
    *,
    model_id: str,
    state_summary: str,
    simulated_metrics: tuple[DigitalTwinMetric, ...],
) -> str:
    return _fingerprint(
        {
            "model_id": model_id,
            "simulated_metrics": [
                item.model_dump(mode="json") for item in simulated_metrics
            ],
            "state_summary": state_summary,
        }
    )


class DigitalTwinProjection(_HardwareContract):
    model_id: str
    state_summary: str
    simulated_metrics: tuple[DigitalTwinMetric, ...]
    fingerprint: str

    _model_id = field_validator("model_id")(
        lambda value: _identifier(value, field="model_id")
    )
    _state_summary = field_validator("state_summary")(
        lambda value: _safe_text(value, field="state_summary")
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("simulated_metrics", mode="before")
    @classmethod
    def _metric_tuple(cls, value: object) -> object:
        return _tuple(value, field="simulated_metrics")

    @model_validator(mode="after")
    def _metrics_and_fingerprint(self) -> DigitalTwinProjection:
        names = tuple(item.metric_name for item in self.simulated_metrics)
        if (
            not names
            or len(names) > 64
            or names != tuple(sorted(names))
            or len(names) != len(set(names))
        ):
            raise ValueError("simulated_metrics must be sorted and unique")
        if self.fingerprint != digital_twin_fingerprint(
            model_id=self.model_id,
            state_summary=self.state_summary,
            simulated_metrics=self.simulated_metrics,
        ):
            raise ValueError("digital twin fingerprint mismatch")
        return self


class HardwareTelemetryRequest(_HardwareContract):
    hardware_id: str
    scenario_id: str
    twin_fingerprint: str
    timestamp: datetime

    _hardware_id = field_validator("hardware_id")(
        lambda value: _identifier(value, field="hardware_id")
    )
    _scenario_id = field_validator("scenario_id")(
        lambda value: _identifier(value, field="scenario_id")
    )
    _twin_fingerprint = field_validator("twin_fingerprint")(_checked_fingerprint)
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )


class HardwareObservation(_HardwareContract):
    sensor_id: str
    metric_name: str
    value: int | float
    unit: HardwareMetricUnit
    timestamp: datetime

    _sensor_id = field_validator("sensor_id")(
        lambda value: _identifier(value, field="sensor_id")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )

    @field_validator("metric_name")
    @classmethod
    def _metric_name(cls, value: str) -> str:
        if type(value) is not str or re.fullmatch(_METRIC_NAME, value) is None:
            raise ValueError("metric_name is invalid")
        return value

    @field_validator("value")
    @classmethod
    def _metric_value(cls, value: int | float) -> int | float:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("observation value is invalid")
        return value


def hardware_observation_fingerprint(
    observations: tuple[HardwareObservation, ...],
) -> str:
    return _fingerprint([item.model_dump(mode="json") for item in observations])


def hil_projection_fingerprint(
    *,
    scenario_id: str,
    input_reference: str,
    observation_reference: str,
    status: HILProjectionStatus,
) -> str:
    return _fingerprint(
        {
            "input_reference": input_reference,
            "observation_reference": observation_reference,
            "scenario_id": scenario_id,
            "status": status.value,
        }
    )


class HILProjection(_HardwareContract):
    scenario_id: str
    input_reference: str
    observation_reference: str
    status: HILProjectionStatus
    fingerprint: str

    _scenario_id = field_validator("scenario_id")(
        lambda value: _identifier(value, field="scenario_id")
    )
    _input_reference = field_validator("input_reference")(_checked_fingerprint)
    _observation_reference = field_validator("observation_reference")(
        _checked_fingerprint
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> HILProjection:
        if self.fingerprint != hil_projection_fingerprint(
            scenario_id=self.scenario_id,
            input_reference=self.input_reference,
            observation_reference=self.observation_reference,
            status=self.status,
        ):
            raise ValueError("HIL fingerprint mismatch")
        return self


class HardwareValidationRequest(_HardwareContract):
    context: HardwareContextProjection
    digital_twin: DigitalTwinProjection
    hil_projection: HILProjection
    observations: tuple[HardwareObservation, ...]
    observation_fingerprint: str
    approval_fingerprint: str
    timestamp: datetime

    _observation_fingerprint = field_validator("observation_fingerprint")(
        _checked_fingerprint
    )
    _approval_fingerprint = field_validator("approval_fingerprint")(
        _checked_fingerprint
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )

    @field_validator("observations", mode="before")
    @classmethod
    def _observation_tuple(cls, value: object) -> object:
        return _tuple(value, field="observations")

    @model_validator(mode="after")
    def _bindings(self) -> HardwareValidationRequest:
        if (
            self.observation_fingerprint
            != hardware_observation_fingerprint(self.observations)
            or self.hil_projection.input_reference != self.digital_twin.fingerprint
            or self.hil_projection.observation_reference != self.observation_fingerprint
        ):
            raise ValueError("validation request binding mismatch")
        return self


def hardware_validation_fingerprint(
    *,
    hardware_id: str,
    twin_fingerprint: str,
    observation_fingerprint: str,
    status: HardwareValidationStatus,
    validation_types: tuple[HardwareValidationType, ...],
) -> str:
    return _fingerprint(
        {
            "hardware_id": hardware_id,
            "observation_fingerprint": observation_fingerprint,
            "status": status.value,
            "twin_fingerprint": twin_fingerprint,
            "validation_types": [item.value for item in validation_types],
        }
    )


class HardwareValidationProjection(_HardwareContract):
    hardware_id: str
    twin_fingerprint: str
    observation_fingerprint: str
    status: HardwareValidationStatus
    validation_types: tuple[HardwareValidationType, ...]
    fingerprint: str

    _hardware_id = field_validator("hardware_id")(
        lambda value: _identifier(value, field="hardware_id")
    )
    _twin_fingerprint = field_validator("twin_fingerprint")(_checked_fingerprint)
    _observation_fingerprint = field_validator("observation_fingerprint")(
        _checked_fingerprint
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("validation_types", mode="before")
    @classmethod
    def _validation_tuple(cls, value: object) -> object:
        return _tuple(value, field="validation_types")

    @model_validator(mode="after")
    def _types_and_fingerprint(self) -> HardwareValidationProjection:
        keys = tuple(item.value for item in self.validation_types)
        if not keys or keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("validation_types must be sorted and unique")
        if self.fingerprint != hardware_validation_fingerprint(
            hardware_id=self.hardware_id,
            twin_fingerprint=self.twin_fingerprint,
            observation_fingerprint=self.observation_fingerprint,
            status=self.status,
            validation_types=self.validation_types,
        ):
            raise ValueError("validation fingerprint mismatch")
        return self


def hardware_validation_approval_fingerprint(
    *,
    hardware_id: str,
    snapshot_fingerprint: str,
    decision: HardwareValidationDecision,
    reviewer: str,
    timestamp: datetime,
) -> str:
    return _fingerprint(
        {
            "decision": decision.value,
            "hardware_id": hardware_id,
            "reviewer": reviewer,
            "snapshot_fingerprint": snapshot_fingerprint,
            "timestamp": timestamp.isoformat(),
        }
    )


class HardwareValidationApproval(_HardwareContract):
    hardware_id: str
    snapshot_fingerprint: str
    decision: HardwareValidationDecision
    reviewer: str
    timestamp: datetime
    fingerprint: str

    _hardware_id = field_validator("hardware_id")(
        lambda value: _identifier(value, field="hardware_id")
    )
    _snapshot_fingerprint = field_validator("snapshot_fingerprint")(
        _checked_fingerprint
    )
    _reviewer = field_validator("reviewer")(
        lambda value: _identifier(value, field="reviewer")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> HardwareValidationApproval:
        if self.fingerprint != hardware_validation_approval_fingerprint(
            hardware_id=self.hardware_id,
            snapshot_fingerprint=self.snapshot_fingerprint,
            decision=self.decision,
            reviewer=self.reviewer,
            timestamp=self.timestamp,
        ):
            raise ValueError("approval fingerprint mismatch")
        return self


class HardwareProgressEvent(_HardwareContract):
    sequence: int
    hardware_id: str
    state: HardwareIntelligenceState
    event: HardwareProgressEventType
    timestamp: datetime

    _hardware_id = field_validator("hardware_id")(
        lambda value: _identifier(value, field="hardware_id")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )

    @field_validator("sequence")
    @classmethod
    def _sequence(cls, value: int) -> int:
        if type(value) is not int or value < 1:
            raise ValueError("sequence is invalid")
        return value


def hardware_snapshot_fingerprint(
    *,
    request: HardwareAnalysisRequest,
    state: HardwareIntelligenceState,
    digital_twin: DigitalTwinProjection | None,
    hil_projection: HILProjection | None,
    observations: tuple[HardwareObservation, ...],
    observation_fingerprint: str | None,
    validation: HardwareValidationProjection | None,
    failure_code: HardwareFailureCode | None,
    progress_sequence: int,
) -> str:
    return _fingerprint(
        {
            "digital_twin": (
                digital_twin.model_dump(mode="json")
                if digital_twin is not None
                else None
            ),
            "failure_code": failure_code.value if failure_code is not None else None,
            "hil_projection": (
                hil_projection.model_dump(mode="json")
                if hil_projection is not None
                else None
            ),
            "observation_fingerprint": observation_fingerprint,
            "observations": [item.model_dump(mode="json") for item in observations],
            "progress_sequence": progress_sequence,
            "request": request.model_dump(mode="json"),
            "state": state.value,
            "validation": (
                validation.model_dump(mode="json") if validation is not None else None
            ),
        }
    )


class HardwareIntelligenceSnapshot(_HardwareContract):
    request: HardwareAnalysisRequest
    state: HardwareIntelligenceState
    digital_twin: DigitalTwinProjection | None = None
    hil_projection: HILProjection | None = None
    observations: tuple[HardwareObservation, ...] = ()
    observation_fingerprint: str | None = None
    validation: HardwareValidationProjection | None = None
    failure_code: HardwareFailureCode | None = None
    progress_sequence: int
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("observations", mode="before")
    @classmethod
    def _observation_tuple(cls, value: object) -> object:
        return _tuple(value, field="observations")

    @field_validator("observation_fingerprint")
    @classmethod
    def _observation_fingerprint_format(cls, value: str | None) -> str | None:
        return None if value is None else _checked_fingerprint(value)

    @field_validator("progress_sequence")
    @classmethod
    def _progress_sequence(cls, value: int) -> int:
        if type(value) is not int or value < 1:
            raise ValueError("progress_sequence is invalid")
        return value

    @model_validator(mode="after")
    def _state_and_fingerprint(self) -> HardwareIntelligenceSnapshot:
        if (
            self.state
            in {HardwareIntelligenceState.FAILED, HardwareIntelligenceState.INVALID}
        ) != (self.failure_code is not None):
            raise ValueError("snapshot failure state is invalid")
        observed_states = {
            HardwareIntelligenceState.OBSERVATION_READY,
            HardwareIntelligenceState.VALIDATING,
            HardwareIntelligenceState.VALIDATED,
            HardwareIntelligenceState.INVALID,
        }
        if self.state in observed_states and (
            self.digital_twin is None
            or self.hil_projection is None
            or not self.observations
            or self.observation_fingerprint is None
        ):
            raise ValueError("observation snapshot is incomplete")
        if self.observations:
            if self.observation_fingerprint != hardware_observation_fingerprint(
                self.observations
            ):
                raise ValueError("observation fingerprint mismatch")
        elif self.observation_fingerprint is not None:
            raise ValueError("observation fingerprint is unexpected")
        if self.hil_projection is not None:
            if self.digital_twin is None or self.observation_fingerprint is None:
                raise ValueError("HIL projection binding is incomplete")
            if (
                self.hil_projection.scenario_id != self.request.scenario_id
                or self.hil_projection.input_reference != self.digital_twin.fingerprint
                or self.hil_projection.observation_reference
                != self.observation_fingerprint
            ):
                raise ValueError("HIL projection binding mismatch")
        if self.validation is not None:
            if (
                self.digital_twin is None
                or self.observation_fingerprint is None
                or self.validation.hardware_id != self.request.hardware_id
                or self.validation.twin_fingerprint != self.digital_twin.fingerprint
                or self.validation.observation_fingerprint
                != self.observation_fingerprint
            ):
                raise ValueError("validation binding mismatch")
        if self.state is HardwareIntelligenceState.VALIDATED and (
            self.validation is None
            or self.validation.status is not HardwareValidationStatus.VALID
        ):
            raise ValueError("validated snapshot is incomplete")
        if self.fingerprint != hardware_snapshot_fingerprint(
            request=self.request,
            state=self.state,
            digital_twin=self.digital_twin,
            hil_projection=self.hil_projection,
            observations=self.observations,
            observation_fingerprint=self.observation_fingerprint,
            validation=self.validation,
            failure_code=self.failure_code,
            progress_sequence=self.progress_sequence,
        ):
            raise ValueError("snapshot fingerprint mismatch")
        return self
