from embedded_copilot.firmware.models import FirmwareRequest
from embedded_copilot.firmware.platform import (
    ESP32Platform,
    FirmwarePlatform,
    STM32Platform,
)


def test_esp32_platform_describes_and_validates_capabilities() -> None:
    platform = ESP32Platform()

    assert isinstance(platform, FirmwarePlatform)
    assert platform.supported_features() == (
        "ESP32",
        "ESP-IDF",
        "FreeRTOS",
        "GPIO",
        "WiFi",
        "SPI",
    )
    assert platform.validate_request(
        FirmwareRequest(
            requirement="sensor",
            platform="esp32",
            framework="esp-idf",
            peripherals=["gpio", "wifi"],
        )
    ).success


def test_stm32_platform_describes_and_validates_capabilities() -> None:
    platform = STM32Platform()

    assert platform.supported_features() == ("STM32", "HAL", "UART", "SPI", "ADC")
    assert platform.validate_request(
        FirmwareRequest(
            requirement="serial",
            platform="STM32",
            framework="HAL",
            peripherals=["UART"],
        )
    ).success


def test_platform_reports_incompatible_request_fields() -> None:
    result = ESP32Platform().validate_request(
        FirmwareRequest(
            requirement="serial",
            platform="STM32",
            framework="HAL",
            peripherals=["UART"],
        )
    )

    assert result.success is False
    assert len(result.errors) == 3


def test_platform_rejects_cross_category_features() -> None:
    result = ESP32Platform().validate_request(
        FirmwareRequest(
            requirement="invalid categories",
            platform="ESP32",
            framework="GPIO",
            peripherals=["ESP-IDF"],
        )
    )

    assert result.success is False
    assert "unsupported framework: GPIO" in result.errors
    assert "unsupported peripheral: ESP-IDF" in result.errors
