"""Deterministic orchestration for hardware-intelligence projections."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.hardware_intelligence.contracts import (
    DigitalTwinProviderPort,
    HardwareProgressSink,
    HardwareTelemetryPort,
    HardwareValidationPort,
)
from embedded_copilot.hardware_intelligence.digital_twin.service import (
    validate_digital_twin,
)
from embedded_copilot.hardware_intelligence.exceptions import (
    HardwareIntelligenceRejected,
    HardwareObservationRejected,
    HardwareProgressUnavailable,
)
from embedded_copilot.hardware_intelligence.hil.projection import (
    create_hil_projection,
)
from embedded_copilot.hardware_intelligence.models import (
    DigitalTwinProjection,
    DigitalTwinRequest,
    HardwareAnalysisRequest,
    HardwareFailureCode,
    HardwareIntelligenceSnapshot,
    HardwareIntelligenceState,
    HardwareObservation,
    HardwareProgressEvent,
    HardwareProgressEventType,
    HardwareTelemetryRequest,
    HardwareValidationApproval,
    HardwareValidationDecision,
    HardwareValidationProjection,
    HardwareValidationRequest,
    HardwareValidationStatus,
    hardware_observation_fingerprint,
    hardware_snapshot_fingerprint,
)
from embedded_copilot.hardware_intelligence.telemetry.observation import (
    normalize_observations,
)
from embedded_copilot.hardware_intelligence.validation.service import (
    validate_projection,
)


class _HardwareIntelligenceService:
    """Private implementation behind the public protocol facade."""

    def __init__(
        self,
        *,
        twin_provider: DigitalTwinProviderPort,
        telemetry_provider: HardwareTelemetryPort,
        validation_port: HardwareValidationPort,
        progress_sink: HardwareProgressSink,
    ) -> None:
        self._twin_provider = twin_provider
        self._telemetry_provider = telemetry_provider
        self._validation_port = validation_port
        self._progress_sink = progress_sink

    def prepare_hardware_analysis(
        self, request: HardwareAnalysisRequest
    ) -> HardwareIntelligenceSnapshot:
        request = self._copy_request(request)
        self._emit(
            request=request,
            sequence=1,
            state=HardwareIntelligenceState.CREATED,
            event=HardwareProgressEventType.ANALYSIS_CREATED,
        )
        self._emit(
            request=request,
            sequence=2,
            state=HardwareIntelligenceState.CONTEXT_READY,
            event=HardwareProgressEventType.CONTEXT_PROJECTED,
        )

        twin_request = DigitalTwinRequest(
            hardware_id=request.hardware_id,
            scenario_id=request.scenario_id,
            context=request.context.model_copy(deep=True),
            timestamp=request.timestamp,
        )
        try:
            candidate = self._twin_provider.simulate(twin_request)
        except Exception:
            return self._terminal_failure(
                request=request,
                sequence=3,
                failure_code=HardwareFailureCode.TWIN_UNAVAILABLE,
            )
        try:
            twin = validate_digital_twin(candidate)
        except HardwareIntelligenceRejected:
            return self._terminal_failure(
                request=request,
                sequence=3,
                failure_code=HardwareFailureCode.TWIN_REJECTED,
            )
        self._emit(
            request=request,
            sequence=3,
            state=HardwareIntelligenceState.TWIN_READY,
            event=HardwareProgressEventType.TWIN_PROJECTED,
        )

        telemetry_request = HardwareTelemetryRequest(
            hardware_id=request.hardware_id,
            scenario_id=request.scenario_id,
            twin_fingerprint=twin.fingerprint,
            timestamp=request.timestamp,
        )
        try:
            raw_observations = self._telemetry_provider.observe(telemetry_request)
        except Exception:
            return self._terminal_failure(
                request=request,
                sequence=4,
                failure_code=HardwareFailureCode.TELEMETRY_UNAVAILABLE,
                twin=twin,
            )
        try:
            observations = normalize_observations(raw_observations)
        except HardwareObservationRejected:
            return self._terminal_failure(
                request=request,
                sequence=4,
                failure_code=HardwareFailureCode.OBSERVATION_REJECTED,
                twin=twin,
            )
        observation_fingerprint = hardware_observation_fingerprint(observations)
        hil_projection = create_hil_projection(
            scenario_id=request.scenario_id,
            twin_fingerprint=twin.fingerprint,
            observation_fingerprint=observation_fingerprint,
        )
        snapshot = self._snapshot(
            request=request,
            state=HardwareIntelligenceState.OBSERVATION_READY,
            sequence=4,
            twin=twin,
            observations=observations,
            observation_fingerprint=observation_fingerprint,
            hil_projection=hil_projection,
        )
        self._emit(
            request=request,
            sequence=4,
            state=snapshot.state,
            event=HardwareProgressEventType.OBSERVATION_PROJECTED,
        )
        return snapshot

    def validate_hardware(
        self,
        snapshot: HardwareIntelligenceSnapshot,
        approval: HardwareValidationApproval,
    ) -> HardwareIntelligenceSnapshot:
        snapshot = self._copy_snapshot(snapshot)
        approval = self._copy_approval(approval)
        if (
            snapshot.state is not HardwareIntelligenceState.OBSERVATION_READY
            or approval.hardware_id != snapshot.request.hardware_id
            or approval.snapshot_fingerprint != snapshot.fingerprint
        ):
            raise HardwareIntelligenceRejected("hardware validation rejected")

        if approval.decision is HardwareValidationDecision.DENIED:
            terminal = self._snapshot_from_observed(
                snapshot=snapshot,
                state=HardwareIntelligenceState.INVALID,
                sequence=5,
                failure_code=HardwareFailureCode.APPROVAL_DENIED,
            )
            self._emit(
                request=snapshot.request,
                sequence=5,
                state=terminal.state,
                event=HardwareProgressEventType.ANALYSIS_INVALID,
            )
            return terminal

        self._emit(
            request=snapshot.request,
            sequence=5,
            state=HardwareIntelligenceState.VALIDATING,
            event=HardwareProgressEventType.VALIDATION_STARTED,
        )
        assert snapshot.digital_twin is not None
        assert snapshot.hil_projection is not None
        assert snapshot.observation_fingerprint is not None
        validation_request = HardwareValidationRequest(
            context=snapshot.request.context.model_copy(deep=True),
            digital_twin=snapshot.digital_twin.model_copy(deep=True),
            hil_projection=snapshot.hil_projection.model_copy(deep=True),
            observations=tuple(
                item.model_copy(deep=True) for item in snapshot.observations
            ),
            observation_fingerprint=snapshot.observation_fingerprint,
            approval_fingerprint=approval.fingerprint,
            timestamp=approval.timestamp,
        )
        try:
            candidate = self._validation_port.validate(validation_request)
        except Exception:
            terminal = self._snapshot_from_observed(
                snapshot=snapshot,
                state=HardwareIntelligenceState.FAILED,
                sequence=6,
                failure_code=HardwareFailureCode.VALIDATION_UNAVAILABLE,
            )
            self._emit_terminal(terminal)
            return terminal
        try:
            validation = validate_projection(candidate, request=validation_request)
        except HardwareIntelligenceRejected:
            terminal = self._snapshot_from_observed(
                snapshot=snapshot,
                state=HardwareIntelligenceState.INVALID,
                sequence=6,
                failure_code=HardwareFailureCode.VALIDATION_INVALID,
            )
            self._emit_terminal(terminal)
            return terminal
        if validation.status is HardwareValidationStatus.INVALID:
            terminal = self._snapshot_from_observed(
                snapshot=snapshot,
                state=HardwareIntelligenceState.INVALID,
                sequence=6,
                failure_code=HardwareFailureCode.VALIDATION_INVALID,
                validation=validation,
            )
            self._emit_terminal(terminal)
            return terminal

        terminal = self._snapshot_from_observed(
            snapshot=snapshot,
            state=HardwareIntelligenceState.VALIDATED,
            sequence=6,
            validation=validation,
        )
        self._emit_terminal(terminal)
        return terminal

    @staticmethod
    def _copy_request(value: object) -> HardwareAnalysisRequest:
        if type(value) is not HardwareAnalysisRequest:
            raise HardwareIntelligenceRejected("hardware request rejected")
        try:
            return HardwareAnalysisRequest.model_validate(value.model_copy(deep=True))
        except (TypeError, ValueError, ValidationError):
            raise HardwareIntelligenceRejected("hardware request rejected") from None

    @staticmethod
    def _copy_snapshot(value: object) -> HardwareIntelligenceSnapshot:
        if type(value) is not HardwareIntelligenceSnapshot:
            raise HardwareIntelligenceRejected("hardware validation rejected")
        try:
            return HardwareIntelligenceSnapshot.model_validate(
                value.model_copy(deep=True)
            )
        except (TypeError, ValueError, ValidationError):
            raise HardwareIntelligenceRejected("hardware validation rejected") from None

    @staticmethod
    def _copy_approval(value: object) -> HardwareValidationApproval:
        if type(value) is not HardwareValidationApproval:
            raise HardwareIntelligenceRejected("hardware validation rejected")
        try:
            return HardwareValidationApproval.model_validate(
                value.model_copy(deep=True)
            )
        except (TypeError, ValueError, ValidationError):
            raise HardwareIntelligenceRejected("hardware validation rejected") from None

    def _terminal_failure(
        self,
        *,
        request: HardwareAnalysisRequest,
        sequence: int,
        failure_code: HardwareFailureCode,
        twin: DigitalTwinProjection | None = None,
    ) -> HardwareIntelligenceSnapshot:
        terminal = self._snapshot(
            request=request,
            state=HardwareIntelligenceState.FAILED,
            sequence=sequence,
            twin=twin,
            failure_code=failure_code,
        )
        self._emit_terminal(terminal)
        return terminal

    def _snapshot_from_observed(
        self,
        *,
        snapshot: HardwareIntelligenceSnapshot,
        state: HardwareIntelligenceState,
        sequence: int,
        failure_code: HardwareFailureCode | None = None,
        validation: HardwareValidationProjection | None = None,
    ) -> HardwareIntelligenceSnapshot:
        return self._snapshot(
            request=snapshot.request,
            state=state,
            sequence=sequence,
            twin=snapshot.digital_twin,
            observations=snapshot.observations,
            observation_fingerprint=snapshot.observation_fingerprint,
            hil_projection=snapshot.hil_projection,
            validation=validation,
            failure_code=failure_code,
        )

    @staticmethod
    def _snapshot(
        *,
        request: HardwareAnalysisRequest,
        state: HardwareIntelligenceState,
        sequence: int,
        twin: DigitalTwinProjection | None = None,
        observations: tuple[HardwareObservation, ...] = (),
        observation_fingerprint: str | None = None,
        hil_projection=None,
        validation: HardwareValidationProjection | None = None,
        failure_code: HardwareFailureCode | None = None,
    ) -> HardwareIntelligenceSnapshot:
        fingerprint = hardware_snapshot_fingerprint(
            request=request,
            state=state,
            digital_twin=twin,
            hil_projection=hil_projection,
            observations=observations,
            observation_fingerprint=observation_fingerprint,
            validation=validation,
            failure_code=failure_code,
            progress_sequence=sequence,
        )
        return HardwareIntelligenceSnapshot(
            request=request.model_copy(deep=True),
            state=state,
            digital_twin=twin.model_copy(deep=True) if twin is not None else None,
            hil_projection=(
                hil_projection.model_copy(deep=True)
                if hil_projection is not None
                else None
            ),
            observations=tuple(item.model_copy(deep=True) for item in observations),
            observation_fingerprint=observation_fingerprint,
            validation=(
                validation.model_copy(deep=True) if validation is not None else None
            ),
            failure_code=failure_code,
            progress_sequence=sequence,
            fingerprint=fingerprint,
        )

    def _emit_terminal(self, snapshot: HardwareIntelligenceSnapshot) -> None:
        if snapshot.state is HardwareIntelligenceState.VALIDATED:
            event = HardwareProgressEventType.VALIDATION_COMPLETED
        elif snapshot.state is HardwareIntelligenceState.INVALID:
            event = HardwareProgressEventType.ANALYSIS_INVALID
        else:
            event = HardwareProgressEventType.ANALYSIS_FAILED
        self._emit(
            request=snapshot.request,
            sequence=snapshot.progress_sequence,
            state=snapshot.state,
            event=event,
        )

    def _emit(
        self,
        *,
        request: HardwareAnalysisRequest,
        sequence: int,
        state: HardwareIntelligenceState,
        event: HardwareProgressEventType,
    ) -> None:
        progress = HardwareProgressEvent(
            sequence=sequence,
            hardware_id=request.hardware_id,
            state=state,
            event=event,
            timestamp=request.timestamp,
        )
        try:
            self._progress_sink.emit(progress)
        except Exception:
            raise HardwareProgressUnavailable("hardware progress unavailable") from None
