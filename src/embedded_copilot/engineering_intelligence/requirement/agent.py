"""Rule-bound extraction of explicit engineering requirement tokens."""

from __future__ import annotations

import unicodedata

from embedded_copilot.engineering_intelligence.models import (
    EngineeringRequirementDocument,
    EngineeringRequirementRequest,
    RequirementConstraint,
    requirement_document_fingerprint,
)


class _RequirementAgent:
    def analyze(
        self,
        request: EngineeringRequirementRequest,
    ) -> EngineeringRequirementDocument:
        checked = _typed_copy(request, EngineeringRequirementRequest)
        text = unicodedata.normalize("NFC", checked.requirement_summary).casefold()
        compact = text.replace(" ", "")

        product = "SMART_CAMERA" if _has(text, "camera", "摄像") else "EMBEDDED_SYSTEM"
        functional: set[str] = set()
        if _has(text, "camera", "摄像", "video", "视频"):
            functional.add("VIDEO_CAPTURE")
        if _has(text, "wi-fi", "wifi", "无线传输"):
            functional.add("WIRELESS_TRANSMISSION")
        if not functional:
            functional.add("GENERAL_ENGINEERING_REVIEW")

        performance: set[str] = set()
        if _has(text, "real-time", "realtime", "实时"):
            performance.add("REAL_TIME_OPERATION")

        constraints: set[tuple[str, str]] = set()
        if "esp32-s3" in text or "esp32s3" in compact:
            constraints.add(("MCU", "ESP32-S3"))
        if "ov2640" in compact:
            constraints.add(("CAMERA", "OV2640"))

        software: set[str] = set()
        if "esp-idf" in text or "espidf" in compact:
            software.add("ESP_IDF")
        if "freertos" in compact:
            software.add("FREERTOS")

        power: set[str] = set()
        if _has(text, "low power", "low-power", "低功耗"):
            power.add("LOW_POWER_OPERATION")

        communication: set[str] = set()
        communication_tokens = (
            ("WIFI", ("wi-fi", "wifi")),
            ("BLE", ("bluetooth low energy", "ble")),
            ("UART", ("uart",)),
            ("SPI", ("spi",)),
            ("I2C", ("i2c", "i²c")),
            ("CAN", ("can bus", "can总线")),
            ("USB", ("usb",)),
        )
        for token, markers in communication_tokens:
            if _has(text, *markers):
                communication.add(token)

        values = dict(
            project_id=checked.project.project_id,
            session_id=checked.session_id,
            message_id=checked.message_id,
            product=product,
            functional_requirements=tuple(sorted(functional)),
            performance_requirements=tuple(sorted(performance)),
            hardware_constraints=tuple(
                RequirementConstraint(key=key, value=value)
                for key, value in sorted(constraints)
            ),
            software_constraints=tuple(sorted(software)),
            power_requirements=tuple(sorted(power)),
            communication_requirements=tuple(sorted(communication)),
            review_required=True,
        )
        return EngineeringRequirementDocument(
            **values,
            fingerprint=requirement_document_fingerprint(**values),
        )


def _has(text: str, *markers: str) -> bool:
    return any(marker in text for marker in markers)


def _typed_copy(value: object, expected_type):
    if type(value) is not expected_type:
        raise TypeError("typed requirement request is required")
    copied = value.model_copy(deep=True)
    return expected_type.model_validate(copied)
