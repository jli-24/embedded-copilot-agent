from __future__ import annotations

from embedded_copilot.engineering_execution import (
    DebugRecommendationProjection,
    DebugResult,
    DebugResultStatus,
    EngineeringExecutionState,
    EngineeringExecutionType,
    ExecutionFindingCode,
    ExecutionToolType,
    FlashResult,
    FlashResultStatus,
    create_engineering_execution_runtime,
    debug_recommendation_fingerprint,
    debug_result_fingerprint,
    flash_result_fingerprint,
)
from tests.engineering_execution.conftest import (
    make_debug_input,
    make_flash_input,
    make_metadata,
    make_request,
)


class FlashPortFake:
    def __init__(self) -> None:
        self._metadata = make_metadata(
            EngineeringExecutionType.FLASH,
            binding_id="flash-adapter-1",
            tool_type=ExecutionToolType.FLASH_ADAPTER,
        )
        self.calls = []

    @property
    def metadata(self):
        return self._metadata

    def flash(self, request):
        self.calls.append(request)
        values = dict(
            artifact_fingerprint=request.executable_artifact.artifact_fingerprint,
            tool_type=ExecutionToolType.FLASH_ADAPTER,
            status=FlashResultStatus.SUCCESS,
            finding_codes=(),
        )
        return FlashResult(
            **values,
            fingerprint=flash_result_fingerprint(**values),
        )


class DebugPortFake:
    def __init__(self) -> None:
        self._metadata = make_metadata(
            EngineeringExecutionType.DEBUG,
            binding_id="debug-adapter-1",
            tool_type=ExecutionToolType.DEBUG_ADAPTER,
        )
        self.calls = []

    @property
    def metadata(self):
        return self._metadata

    def debug(self, request):
        self.calls.append(request)
        recommendation_values = dict(
            recommendation_code="REVIEW_COMPILE_DIAGNOSTICS",
            evidence_reference_ids=request.evidence_reference_ids,
            review_required=True,
        )
        recommendation = DebugRecommendationProjection(
            **recommendation_values,
            fingerprint=debug_recommendation_fingerprint(**recommendation_values),
        )
        values = dict(
            artifact_fingerprint=request.artifact.artifact_fingerprint,
            tool_type=ExecutionToolType.DEBUG_ADAPTER,
            status=DebugResultStatus.SUCCESS,
            finding_codes=(),
            evidence_reference_ids=request.evidence_reference_ids,
            recommendations=(recommendation,),
        )
        return DebugResult(
            **values,
            fingerprint=debug_result_fingerprint(**values),
        )


def test_flash_requires_safe_external_artifact_reference(artifact_report) -> None:
    port = FlashPortFake()
    request = make_request(
        artifact_report,
        execution_type=EngineeringExecutionType.FLASH,
        execution_input=make_flash_input(artifact_report.artifact_contract),
    )
    report = (
        create_engineering_execution_runtime(flash_port=port)
        .engineering_execution_port()
        .execute(request)
    )
    assert report.execution_status is EngineeringExecutionState.EXECUTED
    assert report.result.status is FlashResultStatus.SUCCESS
    assert len(port.calls) == 1
    serialized = port.calls[0].model_dump_json().casefold()
    assert not any(
        token in serialized for token in ("path", "binary", "device", "port")
    )


def test_debug_receives_only_safe_validation_projection(
    artifact_report, generation_request
) -> None:
    validation = generation_request.validation_report
    debug_input = make_debug_input(artifact_report.artifact_contract, validation)
    request = make_request(
        artifact_report,
        execution_type=EngineeringExecutionType.DEBUG,
        execution_input=debug_input,
    )
    port = DebugPortFake()
    before = validation.model_dump(mode="python")
    report = (
        create_engineering_execution_runtime(debug_port=port)
        .engineering_execution_port()
        .execute(request)
    )
    assert report.execution_status is EngineeringExecutionState.EXECUTED
    assert report.result.status is DebugResultStatus.SUCCESS
    assert len(port.calls) == 1
    debug_request = port.calls[0]
    assert not hasattr(debug_request, "validation_report")
    assert debug_request.validation_report_fingerprint == validation.fingerprint
    assert validation.model_dump(mode="python") == before
    serialized = report.model_dump_json().casefold()
    assert not any(
        token in serialized for token in ("raw_log", "source_code", "device_memory")
    )
    assert ExecutionFindingCode.APPROVAL_EXPIRED not in report.review.finding_codes
