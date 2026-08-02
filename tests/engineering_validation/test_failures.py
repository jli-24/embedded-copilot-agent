from __future__ import annotations

from embedded_copilot.engineering_validation import (
    AcquisitionStatus,
    EvidenceOutcome,
    EvidenceSourceType,
    EvidenceType,
    ValidationAnalysisStatus,
    ValidationFindingCode,
    ValidationTestType,
    create_hardware_validation_runtime,
)

from .conftest import FakeEvidencePort, make_record


class FailingEvidencePort:
    def __init__(self) -> None:
        self.calls = 0

    def collect(self, _request):
        self.calls += 1
        raise RuntimeError("C:\\private\\device provider failed")


def test_collection_failure_degrades_to_safe_baseline_report(validation_setup) -> None:
    request, _ = validation_setup
    evidence_port = FailingEvidencePort()
    report = (
        create_hardware_validation_runtime(evidence_port=evidence_port)
        .hardware_validation_port()
        .validate(request)
    )
    status = {item.test_type: item.status for item in report.evidence_analysis.results}
    assert (
        status[ValidationTestType.CAMERA_CAPTURE] is ValidationAnalysisStatus.SUPPORTED
    )
    assert (
        status[ValidationTestType.NETWORK_CONNECTIVITY]
        is ValidationAnalysisStatus.UNKNOWN
    )
    assert report.acquisition_status is AcquisitionStatus.UNAVAILABLE
    assert ValidationFindingCode.VALIDATION_UNAVAILABLE in report.review.finding_codes
    assert evidence_port.calls == 1
    assert "private" not in report.model_dump_json().casefold()


def test_baseline_metric_difference_has_dedicated_finding(validation_setup) -> None:
    request, _ = validation_setup
    evidence_port = FakeEvidencePort(
        (
            make_record(
                evidence_id="collection-camera",
                test_type=ValidationTestType.CAMERA_CAPTURE,
                evidence_type=EvidenceType.FPS_RESULT,
                outcome=EvidenceOutcome.PASS,
                source_type=EvidenceSourceType.MOCK,
                metric_name="frames_per_second",
                metric_value=15,
                metric_unit=request.evidence_snapshot.records[
                    0
                ].safe_metadata.metric_unit,
            ),
        )
    )
    report = (
        create_hardware_validation_runtime(evidence_port=evidence_port)
        .hardware_validation_port()
        .validate(request)
    )
    assert (
        ValidationFindingCode.EVIDENCE_BASELINE_CONFLICT in report.review.finding_codes
    )
    camera = next(
        item
        for item in report.evidence_analysis.results
        if item.test_type is ValidationTestType.CAMERA_CAPTURE
    )
    assert camera.status is ValidationAnalysisStatus.SUPPORTED


def test_cross_source_outcome_conflict_is_separately_reported(validation_setup) -> None:
    request, _ = validation_setup
    evidence_port = FakeEvidencePort(
        (
            make_record(
                evidence_id="collection-camera-fail",
                test_type=ValidationTestType.CAMERA_CAPTURE,
                evidence_type=EvidenceType.FPS_RESULT,
                outcome=EvidenceOutcome.FAIL,
                source_type=EvidenceSourceType.MOCK,
                metric_name="frames_per_second",
                metric_value=0,
                metric_unit=request.evidence_snapshot.records[
                    0
                ].safe_metadata.metric_unit,
            ),
        )
    )
    report = (
        create_hardware_validation_runtime(evidence_port=evidence_port)
        .hardware_validation_port()
        .validate(request)
    )
    camera = next(
        item
        for item in report.evidence_analysis.results
        if item.test_type is ValidationTestType.CAMERA_CAPTURE
    )
    assert camera.status is ValidationAnalysisStatus.CONFLICT
    assert ValidationFindingCode.MEASUREMENT_CONFLICT in report.review.finding_codes
    assert (
        ValidationFindingCode.EVIDENCE_BASELINE_CONFLICT in report.review.finding_codes
    )


def test_duplicate_collection_id_is_discarded_fail_closed(validation_setup) -> None:
    request, _ = validation_setup
    baseline = request.evidence_snapshot.records[0]
    duplicate = make_record(
        evidence_id=baseline.evidence_id,
        test_type=baseline.safe_metadata.test_type,
        evidence_type=baseline.evidence_type,
        outcome=baseline.safe_metadata.outcome,
        source_type=EvidenceSourceType.MOCK,
        observation_code=baseline.safe_metadata.observation_code,
        metric_name=baseline.safe_metadata.metric_name,
        metric_value=baseline.safe_metadata.metric_value,
        metric_unit=baseline.safe_metadata.metric_unit,
    )
    evidence_port = FakeEvidencePort((duplicate,))
    report = (
        create_hardware_validation_runtime(evidence_port=evidence_port)
        .hardware_validation_port()
        .validate(request)
    )
    assert report.acquisition_status is AcquisitionStatus.UNAVAILABLE
    assert ValidationFindingCode.VALIDATION_UNAVAILABLE in report.review.finding_codes
    assert (
        ValidationFindingCode.EVIDENCE_BASELINE_CONFLICT in report.review.finding_codes
    )
