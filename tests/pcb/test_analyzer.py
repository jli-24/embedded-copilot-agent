import pytest

from embedded_copilot.hardware.models import HardwareComponent, HardwarePlan
from embedded_copilot.pcb.analyzer import PCBRequirementAnalyzer
from embedded_copilot.pcb.exceptions import PCBAnalysisError


def _hardware_plan() -> HardwarePlan:
    return HardwarePlan(
        project_name="camera_board",
        platform="ESP32",
        mcu="ESP32-S3",
        components=[
            HardwareComponent(
                name="ESP32-S3 MCU",
                category="mcu",
                description="Unverified MCU",
            ),
            HardwareComponent(
                name="Camera module",
                category="camera",
                interface=["SPI", "I2C"],
                description="Unverified camera",
            ),
            HardwareComponent(
                name="Power regulation stage",
                category="power",
                description="Unverified power",
            ),
        ],
        interfaces=["SPI", "I2C", "GPIO"],
        power_requirements=["Confirm regulated rails and decoupling."],
        constraints=["Keep GND plane intact."],
        rationale="Deterministic and unverified.",
    )


def test_analyzer_recognizes_english_and_chinese_rules_in_first_order() -> None:
    analyzer = PCBRequirementAnalyzer()

    requirement = analyzer.analyze(
        "先检查相机与传感器，再检查电源、SPI 通信、ADC 模拟和高速信号"
    )

    assert requirement.project_name == "pcb_review"
    assert requirement.components == [
        "Camera",
        "Sensor",
        "Power",
        "Communication",
        "Analog",
        "High-speed signal",
    ]
    assert requirement.interfaces == ["SPI", "ADC"]


def test_analyzer_maps_hardware_plan_without_mutating_it() -> None:
    analyzer = PCBRequirementAnalyzer()
    plan = _hardware_plan()
    original = plan.model_dump(mode="json")

    requirement = analyzer.analyze(plan)

    assert requirement.project_name == "camera_board"
    assert requirement.platform == "ESP32"
    assert requirement.components == ["MCU", "Camera", "Power"]
    assert requirement.interfaces == ["SPI", "I2C", "GPIO"]
    assert requirement.constraints == [
        "Keep GND plane intact.",
        "Confirm regulated rails and decoupling.",
    ]
    assert plan.model_dump(mode="json") == original


def test_analyzer_metadata_overrides_rule_results() -> None:
    requirement = PCBRequirementAnalyzer().analyze(
        "ESP32 camera SPI",
        metadata={
            "project_name": "override_board",
            "platform": "STM32",
            "components": ["Sensor", "Power", "sensor"],
            "interfaces": ["I2C", "i2c"],
            "constraints": ["Verify pull-ups", "verify pull-ups"],
        },
    )

    assert requirement.project_name == "override_board"
    assert requirement.platform == "STM32"
    assert requirement.components == ["Sensor", "Power"]
    assert requirement.interfaces == ["I2C"]
    assert requirement.constraints == ["Verify pull-ups"]


@pytest.mark.parametrize(
    "metadata",
    [
        {"platform": "unknown"},
        {"components": "Camera"},
        {"components": ["unsupported"]},
        {"interfaces": ["CAN"]},
        {"constraints": [""]},
        {"project_name": ""},
    ],
)
def test_analyzer_rejects_invalid_metadata_overrides(metadata: dict[str, object]) -> None:
    with pytest.raises(PCBAnalysisError):
        PCBRequirementAnalyzer().analyze("ESP32 camera", metadata=metadata)
