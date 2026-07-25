from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from embedded_copilot.hardware_design.evidence import (
    DesignEvidence,
    DesignEvidenceSourceType,
)


def _evidence(**updates: object) -> DesignEvidence:
    payload: dict[str, object] = {
        "evidence_id": "evidence:0123456789abcdef",
        "source_id": "datasheet:esp32-s3",
        "source_type": DesignEvidenceSourceType.DATASHEET,
        "location": "page:45",
        "content_summary": "Structured Datasheet pin record identifies GPIO4.",
        "confidence": 1.0,
    }
    payload.update(updates)
    return DesignEvidence.model_validate(payload)


@pytest.mark.parametrize(
    "location",
    ("page:45", "line:12", "structured:datasheet", "retrieval:metadata"),
)
def test_evidence_accepts_safe_verifiable_locations(location: str) -> None:
    assert _evidence(location=location).location == location


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("source_id", r"C:\\Users\\private\\datasheet.pdf"),
        ("location", r"C:\\Users\\private\\datasheet.pdf:45"),
        ("content_summary", "first line\nsecond line"),
        ("content_summary", r"Read C:\\Users\\private\\main.c"),
        ("content_summary", b"raw source bytes"),
        ("content_summary", "x" * 513),
    ),
)
def test_evidence_rejects_raw_or_path_like_content(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        _evidence(**{field: value})


@pytest.mark.parametrize("confidence", (-0.01, 1.01, math.nan, math.inf))
def test_evidence_rejects_invalid_projection_confidence(confidence: float) -> None:
    with pytest.raises(ValidationError):
        _evidence(confidence=confidence)


def test_evidence_source_types_are_closed() -> None:
    assert [item.value for item in DesignEvidenceSourceType] == [
        "datasheet",
        "firmware",
        "rag",
    ]
    with pytest.raises(ValidationError):
        _evidence(source_type="model_guess")
