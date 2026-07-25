from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.datasheet.models import (
    DatasheetComponent,
    DatasheetInterface,
    UnifiedDatasheetModel,
)
from embedded_copilot.engineering.models import (
    EngineeringSourceReference,
    RealEngineeringEnvelope,
    RealEngineeringError,
)
from embedded_copilot.firmware.review.models import FirmwareReviewResult


def _datasheet() -> UnifiedDatasheetModel:
    return UnifiedDatasheetModel(
        component=DatasheetComponent(
            manufacturer="Espressif",
            part_number="ESP32-S3",
            category="MCU",
            package="QFN-56",
            description="ESP32-S3 microcontroller",
        ),
        interfaces=(DatasheetInterface(name="UART0", protocol="UART"),),
        metadata={"source_id": "attachment:datasheet-1"},
    )


def test_real_engineering_envelope_is_immutable_and_contains_only_safe_facts() -> None:
    review = FirmwareReviewResult(
        files=("main.c",),
        source_ids=("attachment:source-1",),
    )
    envelope = RealEngineeringEnvelope(
        datasheet=_datasheet(),
        firmware_review=review,
        references=(
            EngineeringSourceReference(
                attachment_id="datasheet-1",
                source_id="attachment:datasheet-1",
                filename="esp32-s3.pdf",
            ),
        ),
    )

    serialized = envelope.model_dump_json()

    assert envelope.schema_version == 1
    assert "ESP32-S3" in serialized
    assert "C:\\" not in serialized
    assert "raw_bytes" not in serialized
    assert "content" not in serialized
    with pytest.raises(ValidationError):
        envelope.model_validate({**envelope.model_dump(), "schema_version": 2})
    with pytest.raises(ValidationError):
        envelope.references = ()  # type: ignore[misc]


def test_real_engineering_error_rejects_unsafe_details() -> None:
    with pytest.raises(ValidationError):
        RealEngineeringError(
            domain="firmware",
            code="source_invalid",
            message="private C:\\Users\\secret\\main.c",
            source_ids=("attachment:source-1",),
        )
