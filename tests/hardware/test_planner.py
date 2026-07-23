import pytest

from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.analyzer import HardwareRequirementAnalyzer
from embedded_copilot.hardware.exceptions import HardwarePlanningError
from embedded_copilot.hardware.knowledge.models import HardwareDocument
from embedded_copilot.hardware.models import HardwareRequirement
from embedded_copilot.hardware.planner import HardwarePlanner


def _document(
    *,
    component_name: str | None = None,
    peripheral: str | None = None,
) -> HardwareDocument:
    metadata: dict[str, object] = {"license": "original-test-seed"}
    if component_name is not None:
        metadata["component_name"] = component_name
    if peripheral is not None:
        metadata["peripheral"] = peripheral
    return HardwareDocument(
        id="camera-doc",
        title="Camera Selection Guide",
        category="camera",
        vendor="Example Vendor",
        content="OV2640 appears in narrative content.",
        metadata=metadata,
    )


def test_planner_creates_unverified_esp32_s3_camera_wifi_plan() -> None:
    requirement = HardwareRequirementAnalyzer().analyze(
        "ESP32-S3 camera with WiFi"
    )

    plan = HardwarePlanner().plan(requirement, [])

    assert plan.project_name == "hardware_plan"
    assert plan.mcu == "ESP32-S3"
    assert [component.name for component in plan.components] == [
        "Camera module",
        "PSRAM (candidate)",
        "WiFi-capable MCU/module",
        "Power regulation stage",
    ]
    assert plan.interfaces == ["SPI", "I2C", "GPIO", "WiFi"]
    assert "unverified" in plan.rationale.lower()
    assert "no hardware knowledge documents" in plan.rationale.lower()


def test_planner_creates_stm32_uart_and_temperature_sensor_plans() -> None:
    stm32 = HardwarePlanner().plan(
        HardwareRequirementAnalyzer().analyze("STM32 UART"), []
    )
    sensor = HardwarePlanner().plan(
        HardwareRequirementAnalyzer().analyze("ESP32 温度传感器"), []
    )

    assert [item.name for item in stm32.components] == [
        "UART interface circuit",
        "Power regulation stage",
    ]
    assert [item.name for item in sensor.components] == [
        "Temperature sensor",
        "Power regulation stage",
    ]


def test_planner_creates_generic_display_candidate() -> None:
    plan = HardwarePlanner().plan(
        HardwareRequirementAnalyzer().analyze("ESP32 display"), []
    )

    assert plan.components[0].name == "Display module"
    assert plan.components[0].interface == ["SPI", "I2C"]


def test_planner_uses_structured_document_component_evidence_only() -> None:
    requirement = HardwareRequirementAnalyzer().analyze("ESP32 camera")

    generic = HardwarePlanner().plan(requirement, [_document()])
    evidence_backed = HardwarePlanner().plan(
        requirement,
        [_document(component_name="OV2640 camera", peripheral="Camera")],
    )

    assert generic.components[0].name == "Camera module"
    assert evidence_backed.components[0].name == "OV2640 camera"
    assert evidence_backed.components[0].metadata["evidence_document_id"] == (
        "camera-doc"
    )


def test_planner_metadata_override_has_priority_over_document() -> None:
    requirement = HardwareRequirementAnalyzer().analyze(
        "ESP32 camera",
        metadata={"component_overrides": {"Camera": "Approved camera module"}},
    )

    plan = HardwarePlanner().plan(
        requirement,
        [_document(component_name="OV2640 camera", peripheral="Camera")],
    )

    assert plan.components[0].name == "Approved camera module"
    assert plan.components[0].metadata["selection_basis"] == "metadata_override"


def test_planner_converts_firmware_project_without_inventing_s3() -> None:
    project = FirmwareProject(
        name="camera_project",
        platform="ESP32",
        metadata={"peripherals": ["Camera"]},
    )

    plan = HardwarePlanner().plan_from_project(project)

    assert plan.project_name == "camera_project"
    assert plan.mcu == "ESP32"
    assert [component.name for component in plan.components] == [
        "Camera module",
        "Power regulation stage",
    ]


def test_planner_requires_mcu() -> None:
    requirement = HardwareRequirement(
        requirement="generic hardware",
        project_name="demo",
    )

    with pytest.raises(HardwarePlanningError, match="mcu"):
        HardwarePlanner().plan(requirement, [])
