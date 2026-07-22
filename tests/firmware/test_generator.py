import pytest

from embedded_copilot.firmware.exceptions import FirmwareGenerationError
from embedded_copilot.firmware.generator import FirmwareGenerator
from embedded_copilot.firmware.models import FirmwareRequest


def test_generator_creates_esp32_mock_files() -> None:
    generated = FirmwareGenerator().generate(
        FirmwareRequest(
            requirement="WiFi sensor",
            platform="ESP32",
            framework="ESP-IDF",
            peripherals=["GPIO", "WiFi"],
            metadata={"project_name": "sensor_node"},
        )
    )

    assert generated.project_name == "sensor_node"
    assert generated.platform == "ESP32"
    assert [file.filename for file in generated.files] == ["main.c", "wifi.c"]
    assert all("unverified" in file.content.lower() for file in generated.files)


def test_generator_creates_stm32_uart_mock() -> None:
    generated = FirmwareGenerator().generate(
        FirmwareRequest(
            requirement="serial",
            platform="stm32",
            framework="hal",
            peripherals=["uart"],
        )
    )

    assert generated.project_name == "stm32_firmware"
    assert [file.filename for file in generated.files] == ["main.c"]


def test_generator_adds_main_scaffold_for_wifi_only() -> None:
    generated = FirmwareGenerator().generate(
        FirmwareRequest(
            requirement="WiFi service",
            platform="ESP32",
            peripherals=["WiFi"],
        )
    )

    assert [file.filename for file in generated.files] == ["main.c", "wifi.c"]


@pytest.mark.parametrize(
    "firmware_request",
    [
        FirmwareRequest(requirement="x", platform="unknown", peripherals=["GPIO"]),
        FirmwareRequest(requirement="x", platform="ESP32", peripherals=["UART"]),
        FirmwareRequest(requirement="x", platform="ESP32", peripherals=["SPI"]),
    ],
)
def test_generator_uses_firmware_generation_error(
    firmware_request: FirmwareRequest,
) -> None:
    with pytest.raises(FirmwareGenerationError):
        FirmwareGenerator().generate(firmware_request)


def test_generator_rejects_duplicate_output_filenames() -> None:
    generator = FirmwareGenerator(
        template_bindings={
            ("esp32", "gpio"): ("esp32_gpio", "main.c", "C"),
            ("esp32", "wifi"): ("esp32_wifi", "main.c", "C"),
        }
    )

    with pytest.raises(FirmwareGenerationError, match="duplicate"):
        generator.generate(
            FirmwareRequest(
                requirement="x",
                platform="ESP32",
                peripherals=["GPIO", "WiFi"],
            )
        )


def test_generator_honors_explicit_empty_injections() -> None:
    request = FirmwareRequest(
        requirement="GPIO",
        platform="ESP32",
        peripherals=["GPIO"],
    )

    with pytest.raises(FirmwareGenerationError, match="unsupported platform"):
        FirmwareGenerator(platforms=()).generate(request)
    with pytest.raises(FirmwareGenerationError, match="no mock template"):
        FirmwareGenerator(template_bindings={}).generate(request)
