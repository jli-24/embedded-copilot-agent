from __future__ import annotations

import pytest

from embedded_copilot.engineering_validation import (
    AcquisitionStatus,
    DeviceEvidenceCollectionResult,
    EvidenceMetricUnit,
    EvidenceOutcome,
    EvidenceQualification,
    EvidenceSnapshot,
    EvidenceSourceType,
    EvidenceType,
    HardwareValidationRejected,
    ValidationAnalysisStatus,
    ValidationFindingCode,
    ValidationTestType,
    create_hardware_validation_runtime,
    device_evidence_collection_result_fingerprint,
    evidence_snapshot_fingerprint,
)

from .conftest import FakeEvidencePort, make_record


def _with_baseline(request, records):
    values = dict(
        snapshot_id=request.evidence_snapshot.snapshot_id,
        project_id=request.requirement.project_id,
        requirement_fingerprint=request.requirement.fingerprint,
        hardware_proposal_fingerprint=request.hardware_proposal.fingerprint,
        firmware_proposal_fingerprint=request.firmware_proposal.fingerprint,
        context_fingerprint=request.context.fingerprint,
        records=tuple(sorted(records, key=lambda item: item.evidence_id)),
        captured_at=request.proposed_at,
    )
    snapshot = EvidenceSnapshot(
        **values,
        fingerprint=evidence_snapshot_fingerprint(**values),
    )
    return request.model_copy(update={"evidence_snapshot": snapshot}, deep=True)


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (EvidenceOutcome.PASS, ValidationAnalysisStatus.SUPPORTED),
        (EvidenceOutcome.FAIL, ValidationAnalysisStatus.NOT_MET),
        (EvidenceOutcome.INCONCLUSIVE, ValidationAnalysisStatus.UNKNOWN),
    ],
)
def test_verified_outcome_mapping(validation_setup, outcome, expected) -> None:
    request, _ = validation_setup
    request = _with_baseline(request, ())
    port = FakeEvidencePort(
        (
            make_record(
                evidence_id="network-observation",
                test_type=ValidationTestType.NETWORK_CONNECTIVITY,
                evidence_type=EvidenceType.NETWORK_METRIC,
                outcome=outcome,
                source_type=EvidenceSourceType.MOCK,
                metric_name="latency",
                metric_value=50,
                metric_unit=EvidenceMetricUnit.MILLISECONDS,
            ),
        )
    )
    report = (
        create_hardware_validation_runtime(evidence_port=port)
        .hardware_validation_port()
        .validate(request)
    )
    result = next(
        item
        for item in report.evidence_analysis.results
        if item.test_type is ValidationTestType.NETWORK_CONNECTIVITY
    )
    assert result.status is expected
    if expected is ValidationAnalysisStatus.NOT_MET:
        assert ValidationFindingCode.REQUIREMENT_NOT_MET in report.review.finding_codes


def test_candidate_only_evidence_remains_unknown(validation_setup) -> None:
    request, _ = validation_setup
    request = _with_baseline(request, ())
    candidate = make_record(
        evidence_id="candidate-power",
        test_type=ValidationTestType.POWER_OBSERVATION,
        evidence_type=EvidenceType.POWER_MEASUREMENT,
        outcome=EvidenceOutcome.PASS,
        qualification=EvidenceQualification.CANDIDATE,
        source_type=EvidenceSourceType.MOCK,
        metric_name="current",
        metric_value=100,
        metric_unit=EvidenceMetricUnit.MILLIAMPERES,
    )
    report = (
        create_hardware_validation_runtime(evidence_port=FakeEvidencePort((candidate,)))
        .hardware_validation_port()
        .validate(request)
    )
    power = next(
        item
        for item in report.evidence_analysis.results
        if item.test_type is ValidationTestType.POWER_OBSERVATION
    )
    assert power.status is ValidationAnalysisStatus.UNKNOWN
    assert report.review.candidate_count == 1
    assert not report.evidence_trace


class InvalidOutputPort:
    def collect(self, _request):
        return object()


class WrongBindingPort:
    def collect(self, request):
        values = dict(
            proposal_id="other-proposal",
            project_id=request.project_id,
            test_plan_fingerprint=request.test_plan.fingerprint,
            records=(),
            collected_at=request.requested_at,
        )
        return DeviceEvidenceCollectionResult(
            **values,
            fingerprint=device_evidence_collection_result_fingerprint(**values),
        )


@pytest.mark.parametrize("evidence_port", [InvalidOutputPort(), WrongBindingPort()])
def test_invalid_collection_output_degrades_without_retry(
    validation_setup, evidence_port
) -> None:
    request, _ = validation_setup
    report = (
        create_hardware_validation_runtime(evidence_port=evidence_port)
        .hardware_validation_port()
        .validate(request)
    )
    assert report.acquisition_status is AcquisitionStatus.UNAVAILABLE
    assert ValidationFindingCode.VALIDATION_UNAVAILABLE in report.review.finding_codes


def test_tampered_typed_request_is_rejected_before_collection(validation_setup) -> None:
    request, _ = validation_setup
    evidence_port = FakeEvidencePort()
    tampered = request.model_copy(update={"proposal_id": "different"}, deep=True)
    # A caller-owned identifier may change, but a forged nested evidence binding may not.
    forged_snapshot = request.evidence_snapshot.model_copy(
        update={"project_id": "other-project"}, deep=True
    )
    tampered = tampered.model_copy(
        update={"evidence_snapshot": forged_snapshot}, deep=True
    )
    with pytest.raises(HardwareValidationRejected, match="request rejected"):
        create_hardware_validation_runtime(
            evidence_port=evidence_port
        ).hardware_validation_port().validate(tampered)
    assert evidence_port.calls == []


def test_factory_rejects_non_port() -> None:
    with pytest.raises(TypeError, match="DeviceEvidencePort"):
        create_hardware_validation_runtime(evidence_port=object())
