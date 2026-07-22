import pytest
from pydantic import ValidationError

from embedded_copilot.firmware.models import (
    FirmwareRequest,
    GeneratedCode,
    GeneratedFile,
    ValidationResult,
)


def test_firmware_request_normalizes_values() -> None:
    request = FirmwareRequest(
        requirement=" collect data ",
        platform=" ESP32 ",
        framework=" ESP-IDF ",
        peripherals=[" GPIO ", "WiFi", "GPIO"],
    )

    assert request.requirement == "collect data"
    assert request.platform == "ESP32"
    assert request.framework == "ESP-IDF"
    assert request.peripherals == ["GPIO", "WiFi"]


def test_firmware_models_reject_invalid_contracts() -> None:
    with pytest.raises(ValidationError):
        FirmwareRequest(requirement=" ", platform="ESP32")
    with pytest.raises(ValidationError):
        FirmwareRequest(requirement="x", platform="ESP32", peripherals=[""])
    with pytest.raises(ValidationError):
        FirmwareRequest(requirement="x", platform="ESP32", extra=True)


def test_generated_code_allows_validator_level_empty_values() -> None:
    generated = GeneratedCode(project_name=" demo ", platform=" ESP32 ", files=[])
    empty_file = GeneratedFile(filename=" main.c ", content="", language=" C ")

    assert generated.project_name == "demo"
    assert empty_file.filename == "main.c"
    assert empty_file.content == ""


def test_validation_result_enforces_success_error_invariant() -> None:
    assert ValidationResult(success=True).errors == []
    with pytest.raises(ValidationError):
        ValidationResult(success=True, errors=["unexpected"])
    with pytest.raises(ValidationError):
        ValidationResult(success=False)
