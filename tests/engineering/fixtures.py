from __future__ import annotations

from embedded_copilot.datasheet.models import (
    DatasheetComponent,
    DatasheetInterface,
    DatasheetPin,
    UnifiedDatasheetModel,
)
from embedded_copilot.firmware.review.models import (
    FirmwareGPIOAssignment,
    FirmwareReviewResult,
)


def datasheet_model() -> UnifiedDatasheetModel:
    return UnifiedDatasheetModel(
        component=DatasheetComponent(
            manufacturer="Espressif Systems",
            part_number="ESP32-S3",
            category="MCU",
            package="QFN-56",
            description="ESP32-S3 MCU",
        ),
        pins=(
            DatasheetPin(
                number="12",
                name="GPIO8",
                type="alternate",
                description="Embedded Flash function",
            ),
        ),
        interfaces=(
            DatasheetInterface(name="SPI", protocol="SPI", pins=("12",)),
        ),
        metadata={
            "family": "ESP32-S3",
            "source_id": "attachment:datasheet-1",
        },
    )

def firmware_review() -> FirmwareReviewResult:
    return FirmwareReviewResult(
        files=("camera.c",),
        platform="ESP32",
        framework="ESP-IDF",
        gpio_assignments=(
            FirmwareGPIOAssignment(
                pin="GPIO8",
                role="Camera",
                source_id="attachment:source-1",
                line=7,
                initialized=True,
            ),
        ),
        source_ids=("attachment:source-1",),
    )
