import pytest

from embedded_copilot.firmware.exceptions import FirmwareAnalysisError
from embedded_copilot.firmware.intelligence.analyzer import FirmwareRequirementAnalyzer


def test_analyzer_normalizes_esp32_s3_chinese_sensor_request() -> None:
    analysis = FirmwareRequirementAnalyzer().analyze(
        "ESP32-S3温湿度采集并通过WiFi上传"
    )

    assert analysis.platform == "ESP32"
    assert analysis.features == ["sensor", "wifi"]
    assert analysis.peripherals == ["GPIO", "WiFi"]


def test_analyzer_normalizes_stm32_family_and_framework() -> None:
    analysis = FirmwareRequirementAnalyzer().analyze("STM32F407 HAL ADC acquisition")

    assert analysis.platform == "STM32"
    assert analysis.framework == "HAL"
    assert analysis.features == ["adc"]
    assert analysis.peripherals == ["ADC"]


def test_analyzer_metadata_replaces_rule_results() -> None:
    analysis = FirmwareRequirementAnalyzer().analyze(
        "ESP32 WiFi",
        metadata={
            "platform": "STM32",
            "framework": "HAL",
            "features": ["uart"],
            "peripherals": ["UART"],
            "project_name": "override",
        },
    )

    assert analysis.platform == "STM32"
    assert analysis.features == ["uart"]
    assert analysis.peripherals == ["UART"]
    assert analysis.metadata["project_name"] == "override"


def test_analyzer_rejects_invalid_metadata_override() -> None:
    with pytest.raises(FirmwareAnalysisError):
        FirmwareRequirementAnalyzer().analyze(
            "ESP32 GPIO",
            metadata={"peripherals": "GPIO"},
        )


def test_analyzer_normalizes_valid_metadata_values() -> None:
    analysis = FirmwareRequirementAnalyzer().analyze(
        "generic request",
        metadata={
            "platform": "STM32F407",
            "framework": "hal",
            "features": ["UART", "adc"],
            "peripherals": ["uart", "ADC"],
        },
    )

    assert analysis.platform == "STM32"
    assert analysis.framework == "HAL"
    assert analysis.features == ["uart", "adc"]
    assert analysis.peripherals == ["UART", "ADC"]


def test_analyzer_rejects_unknown_metadata_values() -> None:
    with pytest.raises(FirmwareAnalysisError):
        FirmwareRequirementAnalyzer().analyze(
            "ESP32",
            metadata={"features": ["unknown"]},
        )
