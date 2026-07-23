from __future__ import annotations

import re
from collections.abc import Sequence

from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.analyzer import HardwareRequirementAnalyzer
from embedded_copilot.hardware.exceptions import HardwarePlanningError
from embedded_copilot.hardware.knowledge.models import HardwareDocument
from embedded_copilot.hardware.models import (
    HardwareComponent,
    HardwarePlan,
    HardwareRequirement,
)


_COMPONENT_INTERFACES = {
    "Camera": ["SPI", "I2C", "GPIO"],
    "WiFi": ["WiFi"],
    "Bluetooth": ["Bluetooth"],
    "UART": ["UART"],
    "SPI": ["SPI"],
    "I2C": ["I2C"],
    "ADC": ["ADC"],
    "Sensor": ["I2C", "GPIO"],
    "Display": ["SPI", "I2C"],
}
_GENERIC_COMPONENTS = {
    "Camera": ("Camera module", "camera"),
    "WiFi": ("WiFi-capable MCU/module", "connectivity"),
    "Bluetooth": ("Bluetooth module", "connectivity"),
    "UART": ("UART interface circuit", "interface"),
    "SPI": ("SPI peripheral interface", "interface"),
    "I2C": ("I2C peripheral interface", "interface"),
    "ADC": ("ADC analog front-end", "analog"),
    "Sensor": ("Sensor module", "sensor"),
    "Display": ("Display module", "display"),
}


def _deduplicate(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _platform_from_mcu(mcu: str) -> str | None:
    lowered = mcu.casefold()
    if lowered.startswith("esp32"):
        return "ESP32"
    if lowered.startswith("stm32"):
        return "STM32"
    return None


class HardwarePlanner:
    def __init__(
        self,
        *,
        analyzer: HardwareRequirementAnalyzer | None = None,
    ) -> None:
        self._analyzer = analyzer if analyzer is not None else HardwareRequirementAnalyzer()

    def plan(
        self,
        requirement: HardwareRequirement,
        documents: Sequence[HardwareDocument],
    ) -> HardwarePlan:
        if requirement.mcu is None:
            raise HardwarePlanningError("hardware mcu is required for planning")
        platform = requirement.platform or _platform_from_mcu(requirement.mcu)
        if platform is None:
            raise HardwarePlanningError("hardware platform is required for planning")

        components: list[HardwareComponent] = []
        component_interfaces: list[str] = []
        for peripheral in requirement.peripherals:
            component = _component_for(peripheral, requirement, documents)
            components.append(component)
            component_interfaces.extend(component.interface)
            if peripheral == "Camera" and requirement.mcu == "ESP32-S3":
                psram = HardwareComponent(
                    name="PSRAM (candidate)",
                    category="memory",
                    interface=["SPI"],
                    description=(
                        "Unverified memory candidate; capacity and bus mode require "
                        "authorized MCU and module documentation."
                    ),
                    metadata={"selection_basis": "deterministic_rule"},
                )
                components.append(psram)
                component_interfaces.extend(psram.interface)

        components.append(
            HardwareComponent(
                name="Power regulation stage",
                category="power",
                interface=[],
                description=(
                    "Unverified power-stage placeholder; voltage, current, protection, "
                    "and thermal requirements must be confirmed."
                ),
                metadata={"selection_basis": "deterministic_rule"},
            )
        )

        interfaces = _deduplicate(
            [*requirement.interfaces, *component_interfaces]
        )
        constraints = _deduplicate(
            [
                *requirement.constraints,
                "Confirm voltage and current requirements from authorized documentation.",
                (
                    "Confirm pin mapping, logic levels, clocks, pull-ups, and connectors "
                    "before implementation."
                ),
            ]
        )
        if documents:
            references = ", ".join(
                f"{document.title} ({document.id})" for document in documents
            )
            rationale = (
                "Deterministic hardware planning with retrieved evidence: "
                f"{references}. All selections remain unverified."
            )
        else:
            rationale = (
                "Deterministic hardware planning used no hardware knowledge documents; "
                "all component and interface suggestions are unverified."
            )

        return HardwarePlan(
            project_name=requirement.project_name or "hardware_plan",
            platform=platform,
            mcu=requirement.mcu,
            components=components,
            interfaces=interfaces,
            power_requirements=[
                (
                    "Determine regulated rails, current budget, protection, and thermal "
                    "margin from authorized component documentation."
                )
            ],
            constraints=constraints,
            rationale=rationale,
            metadata={
                "planning_mode": "deterministic_unverified",
                "evidence_document_ids": [document.id for document in documents],
            },
        )

    def plan_from_project(self, project: FirmwareProject) -> HardwarePlan:
        return self.plan(self._analyzer.analyze(project), [])


def _component_for(
    peripheral: str,
    requirement: HardwareRequirement,
    documents: Sequence[HardwareDocument],
) -> HardwareComponent:
    component_name, category = _GENERIC_COMPONENTS[peripheral]
    selection_metadata: dict[str, object] = {
        "selection_basis": "deterministic_rule"
    }

    overrides = requirement.metadata.get("component_overrides", {})
    if isinstance(overrides, dict) and isinstance(overrides.get(peripheral), str):
        component_name = overrides[peripheral]
        selection_metadata = {"selection_basis": "metadata_override"}
    else:
        for document in documents:
            document_peripheral = document.metadata.get("peripheral")
            documented_component = document.metadata.get("component_name")
            if (
                isinstance(document_peripheral, str)
                and document_peripheral.casefold() == peripheral.casefold()
                and isinstance(documented_component, str)
                and documented_component.strip()
            ):
                component_name = documented_component.strip()
                selection_metadata = {
                    "selection_basis": "hardware_document_metadata",
                    "evidence_document_id": document.id,
                }
                break

    if peripheral == "Sensor" and re.search(
        r"temperature|温度|温湿度", requirement.requirement, re.IGNORECASE
    ):
        if selection_metadata["selection_basis"] == "deterministic_rule":
            component_name = "Temperature sensor"

    return HardwareComponent(
        name=component_name,
        category=category,
        interface=list(_COMPONENT_INTERFACES[peripheral]),
        description=(
            f"Unverified {peripheral} candidate; exact part, electrical limits, "
            "pinout, and package require authorized documentation."
        ),
        metadata=selection_metadata,
    )
