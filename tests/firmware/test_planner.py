import pytest

from embedded_copilot.firmware.exceptions import FirmwarePlanningError
from embedded_copilot.firmware.intelligence.analyzer import (
    FirmwareRequirementAnalysis,
    FirmwareRequirementAnalyzer,
)
from embedded_copilot.firmware.knowledge.models import FirmwareDocument
from embedded_copilot.firmware.planner.planner import FirmwarePlanner


def _document() -> FirmwareDocument:
    return FirmwareDocument(
        id="camera-doc",
        title="Camera SDK Guide",
        platform="ESP32",
        framework="ESP-IDF",
        content="ESP32 Camera and WiFi planning notes",
        metadata={"source": "camera.md"},
    )


def test_planner_creates_esp32_camera_plan_with_provenance() -> None:
    analysis = FirmwareRequirementAnalyzer().analyze(
        "ESP32-S3 ESP-IDF WiFi Camera"
    )

    plan = FirmwarePlanner().plan(analysis, [_document()])

    assert plan.platform == "ESP32"
    assert plan.components == ["wifi", "camera"]
    assert plan.files == ["main.c", "wifi.c", "camera.c"]
    assert plan.dependencies == ["ESP-IDF"]
    assert "Camera SDK Guide" in plan.rationale
    request = plan.to_firmware_request(
        requirement=analysis.requirement,
        metadata=analysis.metadata,
    )
    assert request.platform == "ESP32"
    assert request.peripherals == ["WiFi", "Camera"]


def test_planner_creates_stm32_plan() -> None:
    analysis = FirmwareRequirementAnalyzer().analyze("STM32F103 HAL UART ADC")

    plan = FirmwarePlanner().plan(analysis, [])

    assert plan.platform == "STM32"
    assert plan.components == ["uart", "adc"]
    assert plan.files == ["main.c", "adc.c"]
    assert "no firmware knowledge documents" in plan.rationale.lower()


def test_planner_requires_platform() -> None:
    analysis = FirmwareRequirementAnalysis(
        requirement="generic GPIO",
        platform=None,
        framework=None,
        features=["gpio"],
        peripherals=["GPIO"],
    )

    with pytest.raises(FirmwarePlanningError, match="platform"):
        FirmwarePlanner().plan(analysis, [])
