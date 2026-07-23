from embedded_copilot.hardware.models import HardwareComponent, HardwarePlan
from embedded_copilot.hardware.validator import HardwareValidator


def _component(
    name: str = "Camera module",
    interfaces: list[str] | None = None,
) -> HardwareComponent:
    return HardwareComponent(
        name=name,
        category="camera",
        interface=interfaces or ["SPI"],
        description="Unverified candidate",
    )


def _plan() -> HardwarePlan:
    return HardwarePlan(
        project_name="demo",
        platform="ESP32",
        mcu="ESP32-S3",
        components=[_component()],
        interfaces=["SPI"],
        power_requirements=["Verify supply requirements"],
        constraints=["Verify pin mapping"],
        rationale="Deterministic and unverified plan",
    )


def test_validator_accepts_complete_plan() -> None:
    result = HardwareValidator().validate(_plan())

    assert result.success is True
    assert result.errors == []
    assert result.metadata["component_count"] == 1


def test_validator_reports_empty_plan_and_core_fields() -> None:
    plan = HardwarePlan(
        project_name="",
        platform="",
        mcu="",
        rationale="",
    )

    result = HardwareValidator().validate(plan)

    assert result.success is False
    assert "hardware project name must not be empty" in result.errors
    assert "hardware platform must not be empty" in result.errors
    assert "hardware mcu must not be empty" in result.errors
    assert "hardware plan must contain components" in result.errors
    assert "hardware plan is empty" in result.errors


def test_validator_reports_empty_and_duplicate_components() -> None:
    plan = _plan().model_copy(
        update={"components": [_component(""), _component("Camera"), _component("camera")]}
    )

    result = HardwareValidator().validate(plan)

    assert result.success is False
    assert "hardware component name must not be empty" in result.errors
    assert "duplicate hardware component: camera" in result.errors


def test_validator_rejects_illegal_and_unaggregated_interfaces() -> None:
    plan = _plan().model_copy(
        update={
            "components": [_component(interfaces=["DVP", "I2C"])],
            "interfaces": ["SPI", "invalid"],
        }
    )

    result = HardwareValidator().validate(plan)

    assert result.success is False
    assert "unsupported hardware interface: invalid" in result.errors
    assert "unsupported hardware interface: DVP" in result.errors
    assert "component interface not present in plan: I2C" in result.errors
