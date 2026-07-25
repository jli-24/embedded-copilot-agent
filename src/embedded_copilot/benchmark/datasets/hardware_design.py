from __future__ import annotations

from embedded_copilot.hardware.models import HardwareComponent, HardwarePlan


def create_smart_security_hardware_plan() -> HardwarePlan:
    """Return an isolated synthetic plan with every observation explicit."""
    return HardwarePlan(
        project_name="ESP32-S3 Smart Security Terminal",
        platform="ESP32",
        mcu="ESP32-S3",
        components=[
            HardwareComponent(
                name="Camera",
                category="sensor",
                interface=["Camera"],
                description="Explicit synthetic HardwarePlan camera observation.",
            ),
            HardwareComponent(
                name="PIR",
                category="sensor",
                interface=["GPIO"],
                description="Explicit synthetic HardwarePlan PIR observation.",
            ),
            HardwareComponent(
                name="MQ-2",
                category="sensor",
                interface=["ADC"],
                description="Explicit synthetic HardwarePlan MQ-2 observation.",
            ),
            HardwareComponent(
                name="SD Card",
                category="storage",
                interface=["SPI"],
                description="Explicit synthetic HardwarePlan SD Card observation.",
            ),
            HardwareComponent(
                name="MQTT",
                category="connectivity",
                interface=["MQTT"],
                description="Explicit synthetic HardwarePlan MQTT observation.",
            ),
        ],
        interfaces=["Camera", "GPIO", "ADC", "SPI", "MQTT"],
        power_requirements=[
            "Power input and rail requirements require confirmed evidence."
        ],
        constraints=[
            "GPIO, electrical parameters, and connection correctness are unresolved."
        ],
        rationale=(
            "Synthetic read-only fixture; every named module is explicit and all "
            "hardware conclusions remain unresolved."
        ),
        metadata={"fixture_kind": "synthetic_hardware_design"},
    )
