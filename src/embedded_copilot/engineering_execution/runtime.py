"""Stateless, controlled orchestration for Engineering Execution."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.engineering_execution.contracts import (
    BuildPort,
    DebugPort,
    EngineeringExecutionPort,
    FlashPort,
)
from embedded_copilot.engineering_execution.exceptions import (
    EngineeringExecutionRejected,
)
from embedded_copilot.engineering_execution.integration.inputs import (
    BuildExecutionInput,
    DebugExecutionInput,
    EngineeringExecutionRequest,
    FlashExecutionInput,
    _ProjectedExecutionRequest,
    project_request,
    revalidate_artifact_binding,
)
from embedded_copilot.engineering_execution.models import (
    BuildRequest,
    BuildResult,
    BuildResultStatus,
    DebugRequest,
    DebugResult,
    DebugResultStatus,
    EngineeringExecutionContract,
    EngineeringExecutionReport,
    EngineeringExecutionState,
    EngineeringExecutionType,
    ExecutionAdapterMetadata,
    ExecutionApprovalStatus,
    ExecutionBlockedProjection,
    ExecutionFindingCode,
    ExecutionPolicyStatus,
    ExecutionReviewProjection,
    ExecutionToolType,
    FlashRequest,
    FlashResult,
    FlashResultStatus,
    _model_fingerprint,
    build_result_fingerprint,
    debug_result_fingerprint,
    engineering_execution_report_fingerprint,
    execution_blocked_fingerprint,
    flash_result_fingerprint,
    port_request_fingerprint,
)


class _EngineeringExecutionService(EngineeringExecutionPort):
    __slots__ = ("_build_port", "_debug_port", "_flash_port")

    def __init__(
        self,
        *,
        build_port: BuildPort | None,
        flash_port: FlashPort | None,
        debug_port: DebugPort | None,
    ) -> None:
        self._build_port = build_port
        self._flash_port = flash_port
        self._debug_port = debug_port

    def execute(
        self,
        request: EngineeringExecutionRequest,
    ) -> EngineeringExecutionReport:
        try:
            projected = project_request(request)
        except (TypeError, ValueError, ValidationError):
            raise EngineeringExecutionRejected(
                "engineering execution request rejected"
            ) from None
        findings: list[ExecutionFindingCode] = []
        if projected.artifact_review_required:
            findings.append(ExecutionFindingCode.ARTIFACT_REVIEW_REQUIRED)
        if projected.artifact.artifact_status.value == "UNAVAILABLE":
            findings.append(ExecutionFindingCode.ARTIFACT_UNAVAILABLE)
            return self._blocked(projected, findings)
        if projected.request.execution_policy.status is ExecutionPolicyStatus.BLOCKED:
            findings.append(ExecutionFindingCode.POLICY_BLOCKED)
            return self._blocked(projected, findings)
        approval = projected.request.approval_context.status
        if approval is ExecutionApprovalStatus.PENDING:
            findings.append(ExecutionFindingCode.APPROVAL_REQUIRED)
            return self._blocked(projected, findings)
        if approval is ExecutionApprovalStatus.REJECTED:
            findings.append(ExecutionFindingCode.APPROVAL_REJECTED)
            return self._blocked(projected, findings)
        return self._execute_approved(projected, findings)

    def _execute_approved(
        self,
        projected: _ProjectedExecutionRequest,
        findings: list[ExecutionFindingCode],
    ) -> EngineeringExecutionReport:
        port = {
            EngineeringExecutionType.BUILD: self._build_port,
            EngineeringExecutionType.FLASH: self._flash_port,
            EngineeringExecutionType.DEBUG: self._debug_port,
        }[projected.request.execution_type]
        if port is None:
            findings.append(ExecutionFindingCode.EXECUTION_PORT_UNAVAILABLE)
            result = self._unavailable_result(projected)
            return self._report(
                projected,
                result=result,
                state=EngineeringExecutionState.FAILED,
                findings=findings,
                adapter_called=False,
            )
        metadata = self._metadata(port)
        if metadata is None or (
            metadata.execution_type is not projected.request.execution_type
            or metadata.binding_id
            != projected.request.execution_policy.adapter_binding_id
        ):
            findings.append(ExecutionFindingCode.ADAPTER_BINDING_MISMATCH)
            result = self._unavailable_result(projected)
            return self._report(
                projected,
                result=result,
                state=EngineeringExecutionState.FAILED,
                findings=findings,
                adapter_called=False,
            )
        expected_artifact_fingerprint = projected.artifact.fingerprint
        port_request = self._port_request(projected)
        try:
            raw_result = self._call(port, projected, port_request)
        except Exception:
            findings.append(ExecutionFindingCode.EXECUTION_PORT_UNAVAILABLE)
            result = self._unavailable_result(projected)
            return self._report(
                projected,
                result=result,
                state=EngineeringExecutionState.FAILED,
                findings=findings,
                adapter_called=True,
            )
        if not revalidate_artifact_binding(
            port_request.artifact,
            expected_fingerprint=expected_artifact_fingerprint,
        ):
            findings.append(ExecutionFindingCode.ARTIFACT_MUTATED)
            result = self._unavailable_result(projected)
            return self._report(
                projected,
                result=result,
                state=EngineeringExecutionState.FAILED,
                findings=findings,
                adapter_called=True,
            )
        result = self._result(raw_result, projected, metadata)
        if result is None:
            findings.append(ExecutionFindingCode.PORT_RESULT_INVALID)
            result = self._unavailable_result(projected)
            return self._report(
                projected,
                result=result,
                state=EngineeringExecutionState.FAILED,
                findings=findings,
                adapter_called=True,
            )
        state = self._result_state(result, findings)
        return self._report(
            projected,
            result=result,
            state=state,
            findings=findings,
            adapter_called=True,
        )

    @staticmethod
    def _metadata(port: object) -> ExecutionAdapterMetadata | None:
        try:
            value = port.metadata
            if type(value) is not ExecutionAdapterMetadata:
                return None
            return ExecutionAdapterMetadata.model_validate(value.model_copy(deep=True))
        except Exception:
            return None

    @staticmethod
    def _call(port: object, projected: _ProjectedExecutionRequest, request: object):
        if projected.request.execution_type is EngineeringExecutionType.BUILD:
            return port.build(request)
        if projected.request.execution_type is EngineeringExecutionType.FLASH:
            return port.flash(request)
        return port.debug(request)

    @staticmethod
    def _port_request(
        projected: _ProjectedExecutionRequest,
    ) -> BuildRequest | FlashRequest | DebugRequest:
        common = dict(
            execution_id=projected.request.execution_id,
            artifact=projected.artifact.model_copy(deep=True),
            policy_fingerprint=projected.request.execution_policy.fingerprint,
            approval_fingerprint=projected.request.approval_context.fingerprint,
            requested_at=projected.request.requested_at,
        )
        execution_input = projected.request.execution_input
        if isinstance(execution_input, BuildExecutionInput):
            return BuildRequest(
                **common,
                fingerprint=port_request_fingerprint(BuildRequest, **common),
            )
        if isinstance(execution_input, FlashExecutionInput):
            values = {
                **common,
                "executable_artifact": execution_input.executable_artifact.model_copy(
                    deep=True
                ),
            }
            return FlashRequest(
                **values,
                fingerprint=port_request_fingerprint(FlashRequest, **values),
            )
        if (
            not isinstance(execution_input, DebugExecutionInput)
            or projected.validation is None
        ):
            raise EngineeringExecutionRejected(
                "engineering execution request rejected"
            ) from None
        values = {
            **common,
            "build_result": execution_input.build_result.model_copy(deep=True),
            "validation_report_fingerprint": projected.validation.report_fingerprint,
            "validation_finding_codes": projected.validation.finding_codes,
            "evidence_reference_ids": projected.validation.evidence_reference_ids,
            "diagnostic_types": execution_input.diagnostic_types,
        }
        return DebugRequest(
            **values,
            fingerprint=port_request_fingerprint(DebugRequest, **values),
        )

    @staticmethod
    def _result(
        raw_result: object,
        projected: _ProjectedExecutionRequest,
        metadata: ExecutionAdapterMetadata,
    ) -> BuildResult | FlashResult | DebugResult | None:
        expected_type: type[BuildResult] | type[FlashResult] | type[DebugResult] = {
            EngineeringExecutionType.BUILD: BuildResult,
            EngineeringExecutionType.FLASH: FlashResult,
            EngineeringExecutionType.DEBUG: DebugResult,
        }[projected.request.execution_type]
        if type(raw_result) is not expected_type:
            return None
        try:
            result = expected_type.model_validate(raw_result.model_copy(deep=True))
        except (TypeError, ValueError, ValidationError):
            return None
        expected_artifact = (
            projected.request.execution_input.executable_artifact.artifact_fingerprint
            if isinstance(projected.request.execution_input, FlashExecutionInput)
            else projected.artifact.artifact_fingerprint
        )
        if (
            result.artifact_fingerprint != expected_artifact
            or result.tool_type is not metadata.tool_type
        ):
            return None
        return result

    @staticmethod
    def _result_state(
        result: BuildResult | FlashResult | DebugResult,
        findings: list[ExecutionFindingCode],
    ) -> EngineeringExecutionState:
        if isinstance(result, BuildResult):
            if result.status is BuildResultStatus.UNAVAILABLE:
                findings.append(ExecutionFindingCode.EXECUTION_PORT_UNAVAILABLE)
                return EngineeringExecutionState.FAILED
            if result.status is BuildResultStatus.FAILED:
                findings.append(ExecutionFindingCode.BUILD_FAILED)
            return EngineeringExecutionState.EXECUTED
        if isinstance(result, FlashResult):
            if result.status is FlashResultStatus.BLOCKED:
                findings.append(ExecutionFindingCode.EXECUTABLE_ARTIFACT_UNAVAILABLE)
                return EngineeringExecutionState.BLOCKED
            if result.status is FlashResultStatus.FAILED:
                findings.append(ExecutionFindingCode.FLASH_FAILED)
            return EngineeringExecutionState.EXECUTED
        if result.status is DebugResultStatus.UNAVAILABLE:
            findings.append(ExecutionFindingCode.EXECUTION_PORT_UNAVAILABLE)
            return EngineeringExecutionState.FAILED
        if result.status is DebugResultStatus.FAILED:
            findings.append(ExecutionFindingCode.DEBUG_FAILED)
        return EngineeringExecutionState.EXECUTED

    @staticmethod
    def _unavailable_result(
        projected: _ProjectedExecutionRequest,
    ) -> BuildResult | FlashResult | DebugResult:
        execution_type = projected.request.execution_type
        if execution_type is EngineeringExecutionType.BUILD:
            values = dict(
                artifact_fingerprint=projected.artifact.artifact_fingerprint,
                tool_type=ExecutionToolType.BUILD_ADAPTER,
                status=BuildResultStatus.UNAVAILABLE,
                finding_codes=("EXECUTION_PORT_UNAVAILABLE",),
            )
            return BuildResult(
                **values,
                fingerprint=build_result_fingerprint(**values),
            )
        if execution_type is EngineeringExecutionType.FLASH:
            execution_input = projected.request.execution_input
            artifact_fingerprint = (
                execution_input.executable_artifact.artifact_fingerprint
                if isinstance(execution_input, FlashExecutionInput)
                else projected.artifact.artifact_fingerprint
            )
            values = dict(
                artifact_fingerprint=artifact_fingerprint,
                tool_type=ExecutionToolType.FLASH_ADAPTER,
                status=FlashResultStatus.BLOCKED,
                finding_codes=("EXECUTION_PORT_UNAVAILABLE",),
            )
            return FlashResult(
                **values,
                fingerprint=flash_result_fingerprint(**values),
            )
        values = dict(
            artifact_fingerprint=projected.artifact.artifact_fingerprint,
            tool_type=ExecutionToolType.DEBUG_ADAPTER,
            status=DebugResultStatus.UNAVAILABLE,
            finding_codes=("EXECUTION_PORT_UNAVAILABLE",),
            evidence_reference_ids=(),
            recommendations=(),
        )
        return DebugResult(
            **values,
            fingerprint=debug_result_fingerprint(**values),
        )

    def _blocked(
        self,
        projected: _ProjectedExecutionRequest,
        findings: list[ExecutionFindingCode],
    ) -> EngineeringExecutionReport:
        finding_codes = self._findings(findings)
        values = dict(
            execution_type=projected.request.execution_type,
            artifact_fingerprint=projected.request.artifact_contract.fingerprint,
            finding_codes=finding_codes,
        )
        result = ExecutionBlockedProjection(
            **values,
            fingerprint=execution_blocked_fingerprint(**values),
        )
        return self._report(
            projected,
            result=result,
            state=EngineeringExecutionState.BLOCKED,
            findings=findings,
            adapter_called=False,
        )

    @staticmethod
    def _findings(
        findings: list[ExecutionFindingCode],
    ) -> tuple[ExecutionFindingCode, ...]:
        order = {value: index for index, value in enumerate(ExecutionFindingCode)}
        return tuple(sorted(set(findings), key=lambda item: order[item]))

    def _report(
        self,
        projected: _ProjectedExecutionRequest,
        *,
        result: BuildResult | FlashResult | DebugResult | ExecutionBlockedProjection,
        state: EngineeringExecutionState,
        findings: list[ExecutionFindingCode],
        adapter_called: bool,
    ) -> EngineeringExecutionReport:
        finding_codes = self._findings(findings)
        contract_values = dict(
            execution_id=projected.request.execution_id,
            artifact_fingerprint=projected.request.artifact_contract.fingerprint,
            artifact_source_fingerprint=projected.request.artifact_source_fingerprint,
            execution_type=projected.request.execution_type,
            execution_input_fingerprint=projected.request.execution_input.fingerprint,
            policy_fingerprint=projected.request.execution_policy.fingerprint,
            approval_fingerprint=projected.request.approval_context.fingerprint,
            adapter_binding_id=projected.request.execution_policy.adapter_binding_id,
            approval_required=True,
            execution_state=state,
        )
        contract = EngineeringExecutionContract(
            **contract_values,
            fingerprint=_model_fingerprint(
                EngineeringExecutionContract,
                **contract_values,
            ),
        )
        state_history = (
            (EngineeringExecutionState.PROPOSED, EngineeringExecutionState.BLOCKED)
            if state is EngineeringExecutionState.BLOCKED and not adapter_called
            else (
                EngineeringExecutionState.PROPOSED,
                EngineeringExecutionState.APPROVED,
                state,
            )
        )
        review_values = dict(
            execution_id=projected.request.execution_id,
            approval_status=projected.request.approval_context.status,
            policy_status=projected.request.execution_policy.status,
            artifact_review_required=projected.artifact_review_required,
            adapter_called=adapter_called,
            finding_codes=finding_codes,
            state_history=state_history,
            review_required=True,
        )
        review = ExecutionReviewProjection(
            **review_values,
            fingerprint=_model_fingerprint(ExecutionReviewProjection, **review_values),
        )
        values = dict(
            execution_id=projected.request.execution_id,
            execution_contract=contract,
            execution_status=state,
            artifact_fingerprint=projected.request.artifact_contract.fingerprint,
            approval_fingerprint=projected.request.approval_context.fingerprint,
            result=result,
            review=review,
            requested_at=projected.request.requested_at,
            candidate_semantics="unverified",
            review_required=True,
        )
        return EngineeringExecutionReport(
            **values,
            fingerprint=engineering_execution_report_fingerprint(**values),
        )
