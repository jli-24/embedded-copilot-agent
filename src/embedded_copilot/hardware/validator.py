from __future__ import annotations

from embedded_copilot.hardware.models import HardwarePlan, HardwareValidationResult


_ALLOWED_INTERFACES = {
    "GPIO",
    "UART",
    "SPI",
    "I2C",
    "ADC",
    "WiFi",
    "Bluetooth",
    "USB",
}


class HardwareValidator:
    """Validate a hardware plan without invoking EDA or hardware tools."""

    def validate(self, plan: HardwarePlan) -> HardwareValidationResult:
        errors: list[str] = []
        if not plan.project_name.strip():
            errors.append("hardware project name must not be empty")
        if not plan.platform.strip():
            errors.append("hardware platform must not be empty")
        if not plan.mcu.strip():
            errors.append("hardware mcu must not be empty")
        if not plan.rationale.strip():
            errors.append("hardware rationale must not be empty")
        if not plan.components:
            errors.append("hardware plan must contain components")
        if (
            not plan.components
            and not plan.interfaces
            and not plan.power_requirements
            and not plan.constraints
            and not plan.rationale.strip()
        ):
            errors.append("hardware plan is empty")

        component_names: set[str] = set()
        for component in plan.components:
            if not component.name.strip():
                errors.append("hardware component name must not be empty")
            else:
                component_key = component.name.casefold()
                if component_key in component_names:
                    errors.append(f"duplicate hardware component: {component.name}")
                component_names.add(component_key)
            for interface in component.interface:
                if interface not in _ALLOWED_INTERFACES:
                    errors.append(f"unsupported hardware interface: {interface}")
                elif interface not in plan.interfaces:
                    errors.append(
                        f"component interface not present in plan: {interface}"
                    )

        for interface in plan.interfaces:
            if interface not in _ALLOWED_INTERFACES:
                errors.append(f"unsupported hardware interface: {interface}")

        return HardwareValidationResult(
            success=not errors,
            errors=errors,
            metadata={
                "component_count": len(plan.components),
                "interface_count": len(plan.interfaces),
            },
        )
