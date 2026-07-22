from embedded_copilot.firmware.models import GeneratedCode, GeneratedFile
from embedded_copilot.firmware.validator import FirmwareValidator


def test_validator_accepts_nonempty_project_with_main() -> None:
    result = FirmwareValidator().validate(
        GeneratedCode(
            project_name="demo",
            platform="ESP32",
            files=[GeneratedFile(filename="main.c", content="mock", language="C")],
        )
    )

    assert result.success is True
    assert result.errors == []


def test_validator_reports_empty_files() -> None:
    result = FirmwareValidator().validate(
        GeneratedCode(project_name="demo", platform="ESP32", files=[])
    )

    assert result.success is False
    assert "generated project has no files" in result.errors


def test_validator_reports_empty_content_and_missing_main() -> None:
    result = FirmwareValidator().validate(
        GeneratedCode(
            project_name="demo",
            platform="ESP32",
            files=[GeneratedFile(filename="wifi.c", content="", language="C")],
        )
    )

    assert result.success is False
    assert "empty file content: wifi.c" in result.errors
    assert "generated project has no main file" in result.errors


def test_validator_reports_duplicate_filenames() -> None:
    generated_file = GeneratedFile(filename="main.c", content="mock", language="C")
    result = FirmwareValidator().validate(
        GeneratedCode(
            project_name="demo",
            platform="STM32",
            files=[generated_file, generated_file],
        )
    )

    assert result.success is False
    assert "duplicate filename: main.c" in result.errors
