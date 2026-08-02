from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_validation import (
    EvidenceMetricUnit,
    EvidenceOutcome,
    EvidenceQualification,
    EvidenceRecord,
    EvidenceSafeMetadata,
    EvidenceSourceType,
    EvidenceType,
    ValidationTestType,
    evidence_safe_metadata_fingerprint,
)

from .conftest import NOW


def test_evidence_contracts_are_frozen_strict_and_tuple_only(validation_setup) -> None:
    request, _ = validation_setup
    with pytest.raises(ValidationError):
        request.proposal_id = "changed"
    payload = request.model_dump(mode="python")
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        type(request).model_validate(payload)
    record_payload = request.evidence_snapshot.records[0].model_dump(mode="python")
    record_payload["safe_metadata"]["reference_ids"] = ["reference"]
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate(record_payload)


@pytest.mark.parametrize("value", [True, math.nan, math.inf, -math.inf])
def test_metric_value_must_be_finite_and_non_boolean(value) -> None:
    values = dict(
        test_type=ValidationTestType.POWER_OBSERVATION,
        outcome=EvidenceOutcome.PASS,
        observation_code="POWER_OBSERVED",
        metric_name="current",
        metric_value=value,
        metric_unit=EvidenceMetricUnit.MILLIAMPERES,
        sample_count=1,
        reference_ids=("reference-power",),
        observed_at=NOW,
    )
    with pytest.raises(ValidationError):
        EvidenceSafeMetadata(
            **values,
            fingerprint=evidence_safe_metadata_fingerprint(**values),
        )


def test_metric_fields_are_all_or_none() -> None:
    values = dict(
        test_type=ValidationTestType.CAMERA_CAPTURE,
        outcome=EvidenceOutcome.INCONCLUSIVE,
        observation_code="CAMERA_OBSERVED",
        metric_name="frames_per_second",
        metric_value=None,
        metric_unit=EvidenceMetricUnit.FRAMES_PER_SECOND,
        sample_count=1,
        reference_ids=("reference-camera",),
        observed_at=NOW,
    )
    with pytest.raises(ValidationError):
        EvidenceSafeMetadata(
            **values,
            fingerprint=evidence_safe_metadata_fingerprint(**values),
        )


def test_evidence_record_rejects_metricless_measurement() -> None:
    metadata_values = dict(
        test_type=ValidationTestType.CAMERA_CAPTURE,
        outcome=EvidenceOutcome.PASS,
        observation_code="CAMERA_OBSERVED",
        metric_name=None,
        metric_value=None,
        metric_unit=None,
        sample_count=1,
        reference_ids=("reference-camera",),
        observed_at=NOW,
    )
    metadata = EvidenceSafeMetadata(
        **metadata_values,
        fingerprint=evidence_safe_metadata_fingerprint(**metadata_values),
    )
    with pytest.raises(ValidationError):
        EvidenceRecord(
            evidence_id="invalid-measurement",
            evidence_type=EvidenceType.FPS_RESULT,
            source_type=EvidenceSourceType.CALLER_PROVIDED,
            qualification=EvidenceQualification.VERIFIED,
            safe_metadata=metadata,
            fingerprint="sha256:" + "0" * 64,
        )
