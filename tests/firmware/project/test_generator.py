from pathlib import Path

import pytest

from embedded_copilot.firmware.exceptions import FirmwareProjectError
from embedded_copilot.firmware.models import (
    GeneratedCode,
    GeneratedFile,
    ValidationResult,
)
from embedded_copilot.firmware.planner.models import FirmwarePlan
from embedded_copilot.firmware.project.generator import FirmwareProjectGenerator
from embedded_copilot.firmware.project.templates import ProjectTemplateManager


def _plan(
    *,
    platform: str = "ESP32",
    peripherals: list[str] | None = None,
    components: list[str] | None = None,
    project_name: str | None = None,
) -> FirmwarePlan:
    return FirmwarePlan(
        project_name=project_name,
        platform=platform,
        framework="ESP-IDF" if platform.casefold() == "esp32" else "HAL",
        components=components or [],
        peripherals=peripherals or [],
        files=["main.c"],
        dependencies=["ESP-IDF" if platform.casefold() == "esp32" else "HAL"],
        rationale="mock/unverified project plan",
    )


def test_generator_creates_named_esp32_wifi_project() -> None:
    project = FirmwareProjectGenerator().generate(
        _plan(
            peripherals=["GPIO", "WiFi"],
            components=["sensor", "wifi"],
            project_name="sensor_node",
        )
    )

    assert project.name == "sensor_node"
    assert [item.path for item in project.files] == [
        "main/main.c",
        "main/wifi.c",
        "main/wifi.h",
        "README.md",
        "CMakeLists.txt",
    ]
    assert project.structure == [
        "main/",
        "main/main.c",
        "main/wifi.c",
        "main/wifi.h",
        "README.md",
        "CMakeLists.txt",
    ]
    assert project.metadata["generation_mode"] == "mock_unverified"
    assert all(
        "mock" in item.content.lower() and "unverified" in item.content.lower()
        for item in project.files
    )


def test_generator_creates_esp32_camera_project_with_default_name() -> None:
    project = FirmwareProjectGenerator().generate(
        _plan(peripherals=["Camera"], components=["camera"])
    )

    assert project.name == "esp32_project"
    assert [item.path for item in project.files] == [
        "main/main.c",
        "main/camera.c",
        "README.md",
        "CMakeLists.txt",
    ]


def test_generator_creates_stm32_uart_project() -> None:
    project = FirmwareProjectGenerator().generate(
        _plan(platform="STM32", peripherals=["UART"], components=["uart"])
    )

    assert project.name == "stm32_project"
    assert [item.path for item in project.files] == [
        "Core/Src/main.c",
        "Core/Src/uart.c",
        "Core/Inc/uart.h",
        "README.md",
    ]
    assert project.structure == [
        "Core/",
        "Core/Src/",
        "Core/Src/main.c",
        "Core/Src/uart.c",
        "Core/Inc/",
        "Core/Inc/uart.h",
        "README.md",
    ]


class _TrackingGenerator:
    def __init__(self, *, filename: str = "main.c") -> None:
        self.called = False
        self.filename = filename

    def generate(self, request):
        self.called = True
        return GeneratedCode(
            project_name="tracked",
            platform="ESP32",
            files=[
                GeneratedFile(
                    filename=self.filename,
                    content="/* mock/unverified tracking file */",
                    language="C",
                )
            ],
        )


class _TrackingValidator:
    def __init__(self, *, success: bool = True) -> None:
        self.called = False
        self.success = success

    def validate(self, generated):
        self.called = True
        return (
            ValidationResult(success=True)
            if self.success
            else ValidationResult(success=False, errors=["legacy invalid"])
        )


def test_generator_calls_injected_legacy_generator_and_validator() -> None:
    code_generator = _TrackingGenerator()
    code_validator = _TrackingValidator()

    project = FirmwareProjectGenerator(
        code_generator=code_generator,
        code_validator=code_validator,
    ).generate(_plan(peripherals=["GPIO"], components=["gpio"]))

    assert project.files[0].path == "main/main.c"
    assert code_generator.called is True
    assert code_validator.called is True


@pytest.mark.parametrize(
    "plan",
    [
        _plan(platform="unknown", peripherals=["GPIO"]),
        _plan(peripherals=["SPI"], components=["spi"]),
        _plan(platform="STM32", peripherals=["ADC"], components=["adc"]),
    ],
)
def test_generator_rejects_unsupported_platforms_and_components(
    plan: FirmwarePlan,
) -> None:
    with pytest.raises(FirmwareProjectError):
        FirmwareProjectGenerator().generate(plan)


def test_generator_maps_missing_templates_to_project_error() -> None:
    with pytest.raises(FirmwareProjectError):
        FirmwareProjectGenerator(
            template_manager=ProjectTemplateManager()
        ).generate(_plan(peripherals=["GPIO"], components=["gpio"]))


def test_generator_rejects_unknown_legacy_file_and_failed_validation() -> None:
    with pytest.raises(FirmwareProjectError):
        FirmwareProjectGenerator(
            code_generator=_TrackingGenerator(filename="unexpected.c"),
            code_validator=_TrackingValidator(),
        ).generate(_plan(peripherals=["GPIO"], components=["gpio"]))

    with pytest.raises(FirmwareProjectError):
        FirmwareProjectGenerator(
            code_generator=_TrackingGenerator(),
            code_validator=_TrackingValidator(success=False),
        ).generate(_plan(peripherals=["GPIO"], components=["gpio"]))


def test_generator_does_not_materialize_project_directory(tmp_path: Path) -> None:
    FirmwareProjectGenerator().generate(
        _plan(peripherals=["GPIO"], components=["gpio"], project_name="demo")
    )

    assert list(tmp_path.iterdir()) == []
