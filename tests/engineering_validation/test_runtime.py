from __future__ import annotations

from embedded_copilot.engineering_validation import (
    AcquisitionStatus,
    ProjectionState,
    ValidationAnalysisStatus,
    ValidationFindingCode,
    ValidationTestType,
    create_hardware_validation_runtime,
)


def test_validation_builds_plan_collects_once_and_projects_report(
    validation_setup,
) -> None:
    request, evidence_port = validation_setup
    port = create_hardware_validation_runtime(
        evidence_port=evidence_port
    ).hardware_validation_port()

    report = port.validate(request)

    assert tuple(item.test_type for item in report.test_plan.tests) == (
        ValidationTestType.CAMERA_CAPTURE,
        ValidationTestType.NETWORK_CONNECTIVITY,
        ValidationTestType.POWER_OBSERVATION,
        ValidationTestType.FIRMWARE_BUILD,
    )
    assert len(evidence_port.calls) == 1
    assert evidence_port.calls[0].test_plan == report.test_plan
    assert all(
        item.status is ValidationAnalysisStatus.SUPPORTED
        for item in report.evidence_analysis.results
    )
    assert report.acquisition_status is AcquisitionStatus.COMPLETED
    assert all(item.state is ProjectionState.UNKNOWN for item in report.hil.tests)
    assert all(
        item.state is ProjectionState.UNKNOWN for item in report.digital_twin.components
    )
    assert report.candidate_semantics == "unverified"
    assert report.review_required is True


def test_candidate_evidence_does_not_enter_analysis_or_trace(validation_setup) -> None:
    request, evidence_port = validation_setup
    report = (
        create_hardware_validation_runtime(evidence_port=evidence_port)
        .hardware_validation_port()
        .validate(request)
    )
    serialized = report.model_dump_json()
    assert "candidate-network" not in serialized
    assert report.review.candidate_count == 1
    assert tuple(item.evidence_id for item in report.evidence_trace) == (
        "baseline-camera",
        "collection-build",
        "collection-network",
        "collection-power",
    )


def test_report_contains_no_raw_evidence_or_runtime_objects(validation_setup) -> None:
    request, evidence_port = validation_setup
    report = (
        create_hardware_validation_runtime(evidence_port=evidence_port)
        .hardware_validation_port()
        .validate(request)
    )
    serialized = report.model_dump_json().casefold()
    forbidden = (
        "raw_log",
        "file_content",
        "binary",
        "base64",
        "command",
        "register_dump",
        "stack_dump",
        "provider",
    )
    assert not any(item in serialized for item in forbidden)
    assert ValidationFindingCode.HARDWARE_STATE_UNKNOWN in report.review.finding_codes
    assert ValidationFindingCode.FIRMWARE_STATE_UNKNOWN in report.review.finding_codes


def test_validation_keeps_caller_input_unchanged(validation_setup) -> None:
    request, evidence_port = validation_setup
    before = request.model_dump(mode="python")
    create_hardware_validation_runtime(
        evidence_port=evidence_port
    ).hardware_validation_port().validate(request)
    assert request.model_dump(mode="python") == before
