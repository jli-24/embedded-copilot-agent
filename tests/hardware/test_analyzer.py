import pytest

from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.analyzer import HardwareRequirementAnalyzer
from embedded_copilot.hardware.exceptions import HardwareAnalysisError


def test_analyzer_recognizes_esp32_s3_camera_wifi_in_order() -> None:
    result = HardwareRequirementAnalyzer().analyze(
        "ESP32-S3 camera with WiFi"
    )

    assert result.platform == "ESP32"
    assert result.mcu == "ESP32-S3"
    assert result.peripherals == ["Camera", "WiFi"]
    assert result.interfaces == ["SPI", "I2C", "GPIO", "WiFi"]


def test_analyzer_recognizes_stm32_and_all_supported_interfaces() -> None:
    result = HardwareRequirementAnalyzer().analyze(
        "STM32 UART SPI I2C ADC Bluetooth display"
    )

    assert result.platform == "STM32"
    assert result.mcu == "STM32"
    assert result.peripherals == [
        "UART",
        "SPI",
        "I2C",
        "ADC",
        "Bluetooth",
        "Display",
    ]
    assert result.interfaces == [
        "UART",
        "SPI",
        "I2C",
        "ADC",
        "Bluetooth",
    ]


def test_analyzer_recognizes_chinese_sensor_and_display() -> None:
    result = HardwareRequirementAnalyzer().analyze(
        "ESP32 温度传感器和显示屏"
    )

    assert result.peripherals == ["Sensor", "Display"]
    assert result.interfaces == ["I2C", "GPIO", "SPI"]


def test_analyzer_uses_firmware_project_without_inventing_mcu_variant() -> None:
    project = FirmwareProject(
        name="camera_project",
        platform="ESP32",
        framework="ESP-IDF",
        metadata={"peripherals": ["Camera", "WiFi"]},
    )

    result = HardwareRequirementAnalyzer().analyze(project)

    assert result.project_name == "camera_project"
    assert result.platform == "ESP32"
    assert result.mcu == "ESP32"
    assert result.peripherals == ["Camera", "WiFi"]


def test_analyzer_preserves_explicit_firmware_project_mcu_variant() -> None:
    project = FirmwareProject(
        name="s3_project",
        platform="ESP32-S3",
        metadata={"peripherals": ["Camera"]},
    )

    result = HardwareRequirementAnalyzer().analyze(project)

    assert result.platform == "ESP32"
    assert result.mcu == "ESP32-S3"


def test_analyzer_maps_invalid_firmware_project_metadata_to_analysis_error() -> None:
    project = FirmwareProject(
        name="invalid_project",
        platform="ESP32",
        metadata={"peripherals": 42},
    )

    with pytest.raises(HardwareAnalysisError):
        HardwareRequirementAnalyzer().analyze(project)


def test_analyzer_metadata_replaces_rules_and_normalizes_component_overrides() -> None:
    result = HardwareRequirementAnalyzer().analyze(
        "ESP32 camera",
        metadata={
            "project_name": " board ",
            "platform": "STM32",
            "mcu": "stm32",
            "peripherals": ["uart"],
            "interfaces": ["uart", "USB"],
            "constraints": [" verify clock "],
            "component_overrides": {"uart": " USB-UART bridge "},
        },
    )

    assert result.project_name == "board"
    assert result.platform == "STM32"
    assert result.mcu == "STM32"
    assert result.peripherals == ["UART"]
    assert result.interfaces == ["UART", "USB"]
    assert result.constraints == ["verify clock"]
    assert result.metadata["component_overrides"] == {
        "UART": "USB-UART bridge"
    }


@pytest.mark.parametrize(
    "metadata",
    [
        {"platform": "unknown"},
        {"mcu": "unknown"},
        {"platform": "ESP32", "mcu": "STM32"},
        {"peripherals": ["unknown"]},
        {"interfaces": "SPI"},
        {"constraints": [""]},
        {"component_overrides": {"unknown": "part"}},
    ],
)
def test_analyzer_rejects_invalid_metadata(metadata: dict[str, object]) -> None:
    with pytest.raises(HardwareAnalysisError):
        HardwareRequirementAnalyzer().analyze("ESP32 camera", metadata=metadata)


def test_analyzer_preserves_first_peripheral_occurrence_order() -> None:
    result = HardwareRequirementAnalyzer().analyze("STM32 UART then camera")

    assert result.peripherals == ["UART", "Camera"]
    assert result.interfaces == ["UART", "SPI", "I2C", "GPIO"]
