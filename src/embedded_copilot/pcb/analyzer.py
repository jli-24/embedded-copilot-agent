from __future__ import annotations

import re
from collections.abc import Mapping

from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.pcb.exceptions import PCBAnalysisError
from embedded_copilot.pcb.models import PCBRequirement


_COMPONENT_RULES: tuple[tuple[str, str], ...] = (
    ("Power", r"power|电源|供电"),
    ("MCU", r"\bmcu\b|微控制器|单片机|esp32|stm32"),
    ("Camera", r"camera|相机|摄像头"),
    ("Sensor", r"sensor|传感器"),
    ("Communication", r"communication|通信|uart|spi|i2c|i²c"),
    ("High-speed signal", r"high[- ]?speed|高速"),
    ("Analog", r"analog|模拟|adc"),
)
_COMPONENTS = {name.casefold(): name for name, _ in _COMPONENT_RULES}
_INTERFACE_RULES: tuple[tuple[str, str], ...] = (
    ("GPIO", r"gpio"),
    ("UART", r"uart"),
    ("SPI", r"spi"),
    ("I2C", r"i2c|i²c"),
    ("ADC", r"adc"),
    ("WiFi", r"wi[- ]?fi"),
    ("Bluetooth", r"bluetooth|蓝牙"),
    ("USB", r"usb"),
)
_INTERFACES = {name.casefold(): name for name, _ in _INTERFACE_RULES}
_PLATFORMS = {"esp32": "ESP32", "stm32": "STM32"}


def _stable_deduplicate(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _ordered_matches(text: str, rules: tuple[tuple[str, str], ...]) -> list[str]:
    matches: list[tuple[int, str]] = []
    for value, pattern in rules:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is not None:
            matches.append((match.start(), value))
    return _stable_deduplicate([value for _, value in sorted(matches)])


def _platform(text: str) -> str | None:
    for token, value in _PLATFORMS.items():
        if re.search(token, text, re.IGNORECASE):
            return value
    return None


def _canonical_list_override(
    metadata: Mapping[str, object],
    key: str,
    allowed: Mapping[str, str],
) -> list[str] | None:
    if key not in metadata:
        return None
    value = metadata[key]
    if not isinstance(value, list):
        raise PCBAnalysisError(f"metadata {key} must be a list of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise PCBAnalysisError(f"metadata {key} must be a list of strings")
        canonical = allowed.get(item.strip().casefold())
        if canonical is None:
            raise PCBAnalysisError(f"metadata {key} contains an unsupported value")
        result.append(canonical)
    return _stable_deduplicate(result)


def _constraints_override(metadata: Mapping[str, object]) -> list[str] | None:
    if "constraints" not in metadata:
        return None
    value = metadata["constraints"]
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise PCBAnalysisError("metadata constraints must be a list of strings")
    return _stable_deduplicate([item.strip() for item in value])


def _string_override(metadata: Mapping[str, object], key: str) -> str | None:
    if key not in metadata:
        return None
    value = metadata[key]
    if not isinstance(value, str) or not value.strip():
        raise PCBAnalysisError(f"metadata {key} must be a non-empty string")
    return value.strip()


def _hardware_components(plan: HardwarePlan) -> list[str]:
    values: list[str] = []
    for component in plan.components:
        text = f"{component.category} {component.name}"
        values.extend(_ordered_matches(text, _COMPONENT_RULES))
    if "MCU" not in values:
        values.insert(0, "MCU")
    return _stable_deduplicate(values)


class PCBRequirementAnalyzer:
    """Convert text or an immutable HardwarePlan into a PCB requirement."""

    def analyze(
        self,
        source: str | HardwarePlan,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> PCBRequirement:
        if isinstance(source, HardwarePlan):
            project_name = source.project_name
            detected_platform = source.platform
            components = _hardware_components(source)
            interfaces = list(source.interfaces)
            constraints = _stable_deduplicate(
                [*source.constraints, *source.power_requirements]
            )
        elif isinstance(source, str) and source.strip():
            text = source.strip()
            project_name = "pcb_review"
            detected_platform = _platform(text)
            components = _ordered_matches(text, _COMPONENT_RULES)
            interfaces = _ordered_matches(text, _INTERFACE_RULES)
            constraints = []
        else:
            raise PCBAnalysisError("PCB requirement must not be empty")

        payload = dict(metadata or {})
        payload.pop("hardware_plan", None)
        project_override = _string_override(payload, "project_name")
        platform_override = _string_override(payload, "platform")
        if platform_override is not None:
            detected_platform = _PLATFORMS.get(platform_override.casefold())
            if detected_platform is None:
                raise PCBAnalysisError("metadata platform is not supported")

        component_override = _canonical_list_override(
            payload, "components", _COMPONENTS
        )
        interface_override = _canonical_list_override(
            payload, "interfaces", _INTERFACES
        )
        constraint_override = _constraints_override(payload)

        return PCBRequirement(
            project_name=project_override or project_name,
            platform=detected_platform,
            components=(
                component_override if component_override is not None else components
            ),
            interfaces=(
                interface_override if interface_override is not None else interfaces
            ),
            constraints=(
                constraint_override if constraint_override is not None else constraints
            ),
        )
