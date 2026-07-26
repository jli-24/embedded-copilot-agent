from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from embedded_copilot.datasheet.intelligence.models import DatasheetSuggestion
from embedded_copilot.datasheet.intelligence.service import (
    DatasheetIntelligenceError,
    DatasheetIntelligenceService,
)
from embedded_copilot.datasheet.models import UnifiedDatasheetModel
from embedded_copilot.multimodal.context import AttachmentBinding
from embedded_copilot.multimodal.models import (
    MultimodalInput,
    MultimodalInputType,
)

CREATED = datetime(2026, 7, 26, 11, 0, tzinfo=timezone.utc)


def _binding() -> AttachmentBinding:
    return AttachmentBinding(
        session_id="session:1",
        input=MultimodalInput(
            type=MultimodalInputType.FILE,
            reference_id="datasheet:esp32-s3",
            summary="ESP32-S3 datasheet reference.",
        ),
        basename="esp32-s3.pdf",
        size_bytes=4096,
        created_at=CREATED,
    )


def _parsed() -> UnifiedDatasheetModel:
    return UnifiedDatasheetModel.model_validate(
        {
            "component": {
                "manufacturer": "Espressif",
                "part_number": "ESP32-S3",
                "category": "MCU",
                "package": "QFN-56",
                "description": "Wireless MCU",
            },
            "pins": [
                {
                    "number": "43",
                    "name": "U0TXD",
                    "type": "output",
                    "description": "UART transmit",
                }
            ],
            "interfaces": [{"name": "UART0", "protocol": "UART", "pins": ["43"]}],
            "electrical_specs": [
                {
                    "parameter": "Supply range",
                    "min_value": 3.0,
                    "typical_value": 3.3,
                    "max_value": 3.6,
                    "unit": "V",
                }
            ],
        }
    )


def test_datasheet_service_projects_parser_output_as_source_bound_suggestion() -> None:
    class Parser:
        def parse(self, binding: AttachmentBinding) -> UnifiedDatasheetModel:
            return _parsed()

    suggestion = DatasheetIntelligenceService(parser=Parser()).analyze(_binding())

    assert suggestion.output_type == "reasoning_suggestion"
    assert suggestion.source_reference == "datasheet:esp32-s3"
    assert suggestion.chip == "Espressif ESP32-S3"
    assert suggestion.interface == ("UART0 (UART)",)
    assert suggestion.pin_reference == ("43 U0TXD",)
    assert suggestion.electrical_reference == ("Supply range (V)",)
    assert suggestion.requires_engineer_review is True


def test_datasheet_service_isolates_parser_failure_details() -> None:
    class Parser:
        def parse(self, binding: AttachmentBinding) -> UnifiedDatasheetModel:
            raise RuntimeError("C:/private/datasheet token=SECRET_SENTINEL")

    with pytest.raises(
        DatasheetIntelligenceError,
        match="datasheet parser failed",
    ) as captured:
        DatasheetIntelligenceService(parser=Parser()).analyze(_binding())

    assert "SECRET_SENTINEL" not in str(captured.value)
    assert "private" not in str(captured.value)


def test_datasheet_suggestion_rejects_engineering_lifecycle_fields() -> None:
    with pytest.raises(ValidationError):
        DatasheetSuggestion.model_validate(
            {
                "source_reference": "datasheet:1",
                "chip": "ESP32-S3",
                "interface": (),
                "pin_reference": (),
                "electrical_reference": (),
                "requires_engineer_review": True,
                "evidence": "not allowed",
            }
        )
