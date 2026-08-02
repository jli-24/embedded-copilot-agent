"""Pure deterministic projections for Hardware Validation."""

from __future__ import annotations

from dataclasses import dataclass

from embedded_copilot.engineering_validation.integration.inputs import _ValidationInput
from embedded_copilot.engineering_validation.models import (
    AcquisitionStatus,
    DeviceEvidenceCollectionRequest,
    DigitalTwinComponentState,
    DigitalTwinStateProjection,
    EvidenceAnalysisProjection,
    EvidenceAnalysisResult,
    EvidenceOutcome,
    EvidenceQualification,
    EvidenceRecord,
    EvidenceType,
    HILValidationItem,
    HILValidationProjection,
    HardwareValidationReport,
    ProjectionState,
    TestPlanProposal,
    ValidationAnalysisStatus,
    ValidationEvidenceTrace,
    ValidationFindingCode,
    ValidationFindingSeverity,
    ValidationReviewFinding,
    ValidationReviewProjection,
    ValidationTestPlanItem,
    ValidationTestType,
    _fingerprint,
    device_evidence_collection_request_fingerprint,
    hardware_validation_report_fingerprint,
    test_plan_proposal_fingerprint,
    validation_test_plan_item_fingerprint,
)

_NETWORK_PROTOCOLS = ("BLE", "ETHERNET", "MQTT", "TCP_IP", "WIFI")


@dataclass(frozen=True, slots=True)
class _EvidenceMerge:
    records: tuple[EvidenceRecord, ...]
    acquisition_status: AcquisitionStatus
    baseline_conflict: bool


def build_test_plan(source: _ValidationInput) -> TestPlanProposal:
    component_keys = tuple(key for key, _reference in source.component_references)
    components = dict(source.component_references)
    requested: list[ValidationTestType] = []
    targets: dict[ValidationTestType, tuple[str, ...]] = {}
    if (
        "VIDEO_CAPTURE" in source.functional_requirements
        or "CAMERA" in component_keys
        or "CAMERA" in source.task_types
    ):
        requested.append(ValidationTestType.CAMERA_CAPTURE)
        targets[ValidationTestType.CAMERA_CAPTURE] = tuple(
            sorted(
                value for key, value in source.component_references if key == "CAMERA"
            )
        )
    if "NETWORK" in source.task_types or any(
        protocol in _NETWORK_PROTOCOLS for protocol in source.communication_requirements
    ):
        requested.append(ValidationTestType.NETWORK_CONNECTIVITY)
        targets[ValidationTestType.NETWORK_CONNECTIVITY] = tuple(
            sorted(source.communication_requirements)
        )
    if "STORAGE" in component_keys or "STORAGE" in source.task_types:
        requested.append(ValidationTestType.STORAGE_OPERATION)
        targets[ValidationTestType.STORAGE_OPERATION] = tuple(
            item for item in (components.get("STORAGE"),) if item is not None
        )
    if source.power_requirements:
        requested.append(ValidationTestType.POWER_OBSERVATION)
        targets[ValidationTestType.POWER_OBSERVATION] = tuple(source.power_requirements)
    if source.expected_build_artifact != "UNRESOLVED":
        requested.append(ValidationTestType.FIRMWARE_BUILD)
        targets[ValidationTestType.FIRMWARE_BUILD] = (source.proposal_id,)

    requirements = {
        ValidationTestType.CAMERA_CAPTURE: (EvidenceType.FPS_RESULT,),
        ValidationTestType.NETWORK_CONNECTIVITY: (EvidenceType.NETWORK_METRIC,),
        ValidationTestType.STORAGE_OPERATION: (EvidenceType.UART_LOG,),
        ValidationTestType.POWER_OBSERVATION: (EvidenceType.POWER_MEASUREMENT,),
        ValidationTestType.FIRMWARE_BUILD: (EvidenceType.UART_LOG,),
    }
    objectives = {
        ValidationTestType.CAMERA_CAPTURE: "OBSERVE_CAMERA_CAPTURE",
        ValidationTestType.NETWORK_CONNECTIVITY: "OBSERVE_NETWORK_CONNECTIVITY",
        ValidationTestType.STORAGE_OPERATION: "OBSERVE_STORAGE_OPERATION",
        ValidationTestType.POWER_OBSERVATION: "OBSERVE_POWER_BEHAVIOR",
        ValidationTestType.FIRMWARE_BUILD: "OBSERVE_FIRMWARE_BUILD",
    }
    items = tuple(
        _test_item(
            test_type=test_type,
            objective=objectives[test_type],
            targets=targets.get(test_type, ()),
            evidence_types=requirements[test_type],
        )
        for test_type in ValidationTestType
        if test_type in requested
    )
    return TestPlanProposal(
        tests=items,
        fingerprint=test_plan_proposal_fingerprint(tests=items),
    )


def _test_item(
    *,
    test_type: ValidationTestType,
    objective: str,
    targets: tuple[str, ...],
    evidence_types: tuple[EvidenceType, ...],
) -> ValidationTestPlanItem:
    values = dict(
        test_type=test_type,
        objective_code=objective,
        target_references=tuple(sorted(set(targets))),
        required_evidence_types=evidence_types,
        execution_state="NOT_EXECUTED",
    )
    return ValidationTestPlanItem(
        **values,
        fingerprint=validation_test_plan_item_fingerprint(**values),
    )


def build_collection_request(
    source: _ValidationInput, test_plan: TestPlanProposal
) -> DeviceEvidenceCollectionRequest:
    values = dict(
        proposal_id=source.proposal_id,
        project_id=source.project_id,
        requirement_fingerprint=source.requirement_fingerprint,
        hardware_proposal_fingerprint=source.hardware_proposal_fingerprint,
        firmware_proposal_fingerprint=source.firmware_proposal_fingerprint,
        context_fingerprint=source.context_fingerprint,
        baseline_evidence_fingerprint=source.baseline.fingerprint,
        test_plan=test_plan,
        requested_at=source.proposed_at,
    )
    return DeviceEvidenceCollectionRequest(
        **values,
        fingerprint=device_evidence_collection_request_fingerprint(**values),
    )


def merge_evidence(
    baseline: tuple[EvidenceRecord, ...],
    collection: tuple[EvidenceRecord, ...] | None,
) -> _EvidenceMerge:
    if collection is None:
        return _EvidenceMerge(baseline, AcquisitionStatus.UNAVAILABLE, False)
    baseline_ids = {item.evidence_id for item in baseline}
    collection_ids = tuple(item.evidence_id for item in collection)
    if len(collection_ids) != len(set(collection_ids)) or baseline_ids.intersection(
        collection_ids
    ):
        return _EvidenceMerge(baseline, AcquisitionStatus.UNAVAILABLE, True)
    conflict = _has_cross_source_conflict(baseline, collection)
    merged = tuple(sorted((*baseline, *collection), key=lambda item: item.evidence_id))
    return _EvidenceMerge(merged, AcquisitionStatus.COMPLETED, conflict)


def _has_cross_source_conflict(
    baseline: tuple[EvidenceRecord, ...], collection: tuple[EvidenceRecord, ...]
) -> bool:
    for left in baseline:
        for right in collection:
            if (
                left.qualification is not EvidenceQualification.VERIFIED
                or right.qualification is not EvidenceQualification.VERIFIED
                or left.safe_metadata.test_type is not right.safe_metadata.test_type
                or left.evidence_type is not right.evidence_type
            ):
                continue
            left_outcome = left.safe_metadata.outcome
            right_outcome = right.safe_metadata.outcome
            if (
                left_outcome in (EvidenceOutcome.PASS, EvidenceOutcome.FAIL)
                and right_outcome in (EvidenceOutcome.PASS, EvidenceOutcome.FAIL)
                and left_outcome is not right_outcome
            ):
                return True
            if (
                left.safe_metadata.metric_name is not None
                and left.safe_metadata.metric_name == right.safe_metadata.metric_name
                and left.safe_metadata.metric_unit == right.safe_metadata.metric_unit
                and left.safe_metadata.metric_value != right.safe_metadata.metric_value
            ):
                return True
    return False


def build_report(
    source: _ValidationInput,
    test_plan: TestPlanProposal,
    merge: _EvidenceMerge,
) -> HardwareValidationReport:
    verified = tuple(
        item
        for item in merge.records
        if item.qualification is EvidenceQualification.VERIFIED
    )
    candidate_count = sum(
        item.qualification is EvidenceQualification.CANDIDATE for item in merge.records
    )
    analyses = tuple(_analyze(item, verified) for item in test_plan.tests)
    analysis = EvidenceAnalysisProjection(
        results=analyses,
        fingerprint=_fingerprint("EvidenceAnalysisProjection", results=analyses),
    )
    hil_items = tuple(
        HILValidationItem(
            test_type=item.test_type,
            expected_behavior_code=item.objective_code,
            required_evidence_types=item.required_evidence_types,
            state=ProjectionState.UNKNOWN,
        )
        for item in test_plan.tests
    )
    hil = HILValidationProjection(
        tests=hil_items,
        fingerprint=_fingerprint("HILValidationProjection", tests=hil_items),
    )
    behavior_codes = tuple(sorted(item.objective_code for item in test_plan.tests))
    components = tuple(
        DigitalTwinComponentState(
            component_reference=reference,
            expected_behavior_codes=behavior_codes,
            state=ProjectionState.UNKNOWN,
        )
        for _key, reference in source.component_references
    )
    twin = DigitalTwinStateProjection(
        components=components,
        fingerprint=_fingerprint("DigitalTwinStateProjection", components=components),
    )
    required_pairs = {
        (plan_item.test_type, evidence_type)
        for plan_item in test_plan.tests
        for evidence_type in plan_item.required_evidence_types
    }
    trace = tuple(
        ValidationEvidenceTrace(
            evidence_id=item.evidence_id,
            evidence_type=item.evidence_type,
            source_type=item.source_type,
            reference_ids=item.safe_metadata.reference_ids,
            record_fingerprint=item.fingerprint,
        )
        for item in verified
        if (item.safe_metadata.test_type, item.evidence_type) in required_pairs
    )
    codes = _finding_codes(analyses, merge, verified)
    findings = tuple(
        ValidationReviewFinding(code=code, severity=_severity(code)) for code in codes
    )
    review_values = dict(
        proposal_id=source.proposal_id,
        hardware_proposal_fingerprint=source.hardware_proposal_fingerprint,
        firmware_proposal_fingerprint=source.firmware_proposal_fingerprint,
        requirement_fingerprint=source.requirement_fingerprint,
        context_fingerprint=source.context_fingerprint,
        test_count=len(test_plan.tests),
        verified_evidence_count=len(trace),
        candidate_count=candidate_count,
        coverage_count=sum(
            item.status is not ValidationAnalysisStatus.UNKNOWN for item in analyses
        ),
        findings=findings,
        finding_codes=codes,
        review_required=True,
    )
    review = ValidationReviewProjection(
        **review_values,
        fingerprint=_fingerprint("ValidationReviewProjection", **review_values),
    )
    report_values = dict(
        proposal_id=source.proposal_id,
        project_id=source.project_id,
        hardware_proposal_fingerprint=source.hardware_proposal_fingerprint,
        firmware_proposal_fingerprint=source.firmware_proposal_fingerprint,
        requirement_fingerprint=source.requirement_fingerprint,
        plan_fingerprint=source.plan_fingerprint,
        context_fingerprint=source.context_fingerprint,
        baseline_evidence_fingerprint=source.baseline.fingerprint,
        acquisition_status=merge.acquisition_status,
        test_plan=test_plan,
        evidence_analysis=analysis,
        hil=hil,
        digital_twin=twin,
        evidence_trace=trace,
        review=review,
        proposed_at=source.proposed_at,
        candidate_semantics="unverified",
        review_required=True,
    )
    return HardwareValidationReport(
        **report_values,
        fingerprint=hardware_validation_report_fingerprint(**report_values),
    )


def _analyze(
    plan_item: ValidationTestPlanItem, records: tuple[EvidenceRecord, ...]
) -> EvidenceAnalysisResult:
    applicable = tuple(
        item
        for item in records
        if item.safe_metadata.test_type is plan_item.test_type
        and item.evidence_type in plan_item.required_evidence_types
    )
    outcomes = {item.safe_metadata.outcome for item in applicable}
    if EvidenceOutcome.PASS in outcomes and EvidenceOutcome.FAIL in outcomes:
        status = ValidationAnalysisStatus.CONFLICT
    elif EvidenceOutcome.FAIL in outcomes:
        status = ValidationAnalysisStatus.NOT_MET
    elif EvidenceOutcome.PASS in outcomes:
        status = ValidationAnalysisStatus.SUPPORTED
    else:
        status = ValidationAnalysisStatus.UNKNOWN
    ids = tuple(item.evidence_id for item in applicable)
    values = dict(
        test_type=plan_item.test_type,
        status=status,
        evidence_ids=ids,
        evidence_count=len(ids),
    )
    return EvidenceAnalysisResult(
        **values,
        fingerprint=_fingerprint("EvidenceAnalysisResult", **values),
    )


def _finding_codes(
    analyses: tuple[EvidenceAnalysisResult, ...],
    merge: _EvidenceMerge,
    verified: tuple[EvidenceRecord, ...],
) -> tuple[ValidationFindingCode, ...]:
    selected: set[ValidationFindingCode] = {
        ValidationFindingCode.HARDWARE_STATE_UNKNOWN,
        ValidationFindingCode.FIRMWARE_STATE_UNKNOWN,
    }
    for item in analyses:
        if item.status is ValidationAnalysisStatus.UNKNOWN:
            selected.add(ValidationFindingCode.TEST_NOT_EXECUTED)
            selected.add(ValidationFindingCode.EVIDENCE_MISSING)
        elif item.status is ValidationAnalysisStatus.NOT_MET:
            selected.add(ValidationFindingCode.REQUIREMENT_NOT_MET)
        elif item.status is ValidationAnalysisStatus.CONFLICT:
            selected.add(ValidationFindingCode.MEASUREMENT_CONFLICT)
    if merge.baseline_conflict:
        selected.add(ValidationFindingCode.EVIDENCE_BASELINE_CONFLICT)
    if merge.acquisition_status is AcquisitionStatus.UNAVAILABLE:
        selected.add(ValidationFindingCode.VALIDATION_UNAVAILABLE)
    if not verified:
        selected.add(ValidationFindingCode.EVIDENCE_MISSING)
    return tuple(code for code in ValidationFindingCode if code in selected)


def _severity(code: ValidationFindingCode) -> ValidationFindingSeverity:
    if code in (
        ValidationFindingCode.REQUIREMENT_NOT_MET,
        ValidationFindingCode.MEASUREMENT_CONFLICT,
    ):
        return ValidationFindingSeverity.BLOCKING
    return ValidationFindingSeverity.REVIEW
