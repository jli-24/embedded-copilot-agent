import pytest
from pydantic import ValidationError

from embedded_copilot.hardware.models import (
    HardwareComponent,
    HardwarePlan,
    HardwareRequirement,
    HardwareValidationResult,
)


def test_hardware_models_strip_and_deduplicate_contract_fields() -> None:
    requirement = HardwareRequirement(
        requirement=" ESP32 camera ",
        project_name=" demo ",
        platform=" ESP32 ",
        mcu=" ESP32-S3 ",
        peripherals=[" Camera ", "camera", "WiFi"],
        interfaces=[" SPI ", "spi", "GPIO"],
        constraints=[" Verify voltage ", "verify voltage"],
    )
    component = HardwareComponent(
        name=" Camera module ",
        category=" camera ",
        interface=[" SPI ", "spi", "I2C"],
        description=" Candidate only ",
    )

    assert requirement.requirement == "ESP32 camera"
    assert requirement.peripherals == ["Camera", "WiFi"]
    assert requirement.constraints == ["Verify voltage"]
    assert component.name == "Camera module"
    assert component.interface == ["SPI", "I2C"]


def test_hardware_models_are_frozen_and_forbid_extra_fields() -> None:
    plan = HardwarePlan(
        project_name="demo",
        platform="ESP32",
        mcu="ESP32",
        rationale="unverified",
    )

    with pytest.raises(ValidationError):
        plan.mcu = "STM32"
    with pytest.raises(ValidationError):
        HardwareComponent(
            name="x",
            category="sensor",
            description="x",
            extra=True,
        )


def test_hardware_validation_result_enforces_outcome_invariant() -> None:
    assert HardwareValidationResult(success=True).errors == []

    with pytest.raises(ValidationError):
        HardwareValidationResult(success=True, errors=["unexpected"])
    with pytest.raises(ValidationError):
        HardwareValidationResult(success=False)
