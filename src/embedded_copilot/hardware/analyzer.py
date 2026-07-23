from __future__ import annotations

import re
from collections.abc import Mapping

from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.exceptions import HardwareAnalysisError
from embedded_copilot.hardware.models import HardwareRequirement


_PERIPHERAL_RULES: tuple[tuple[str, str], ...] = (
    ("Camera", r"camera|相机|摄像头"),
    ("WiFi", r"wi[- ]?fi"),
    ("Bluetooth", r"bluetooth|蓝牙"),
    ("UART", r"uart"),
    ("SPI", r"spi"),
    ("I2C", r"i2c|i²c"),
    ("ADC", r"adc"),
    ("Sensor", r"temperature sensor|温度传感器|温湿度|sensor|传感器"),
    ("Display", r"display|显示屏|屏幕"),
)
_PERIPHERALS = {value.casefold(): value for value, _ in _PERIPHERAL_RULES}
_INTERFACES = {
    value.casefold(): value
    for value in ("GPIO", "UART", "SPI", "I2C", "ADC", "WiFi", "Bluetooth", "USB")
}
_INTERFACES_BY_PERIPHERAL: Mapping[str, tuple[str, ...]] = {
    "Camera": ("SPI", "I2C", "GPIO"),
    "WiFi": ("WiFi",),
    "Bluetooth": ("Bluetooth",),
    "UART": ("UART",),
    "SPI": ("SPI",),
    "I2C": ("I2C",),
    "ADC": ("ADC",),
    "Sensor": ("I2C", "GPIO"),
    "Display": ("SPI", "I2C"),
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


def _platform(text: str) -> str | None:
    if re.search(r"esp32", text, re.IGNORECASE):
        return "ESP32"
    if re.search(r"stm32", text, re.IGNORECASE):
        return "STM32"
    return None


def _mcu(text: str) -> str | None:
    if re.search(r"esp32[-_ ]?s3", text, re.IGNORECASE):
        return "ESP32-S3"
    if re.search(r"esp32", text, re.IGNORECASE):
        return "ESP32"
    if re.search(r"stm32", text, re.IGNORECASE):
        return "STM32"
    return None


def _peripherals(text: str) -> list[str]:
    matches: list[tuple[int, str]] = []
    for value, pattern in _PERIPHERAL_RULES:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is not None:
            matches.append((match.start(), value))
    return _deduplicate([value for _, value in sorted(matches)])


def _derived_interfaces(peripherals: list[str]) -> list[str]:
    return _deduplicate(
        [
            interface
            for peripheral in peripherals
            for interface in _INTERFACES_BY_PERIPHERAL[peripheral]
        ]
    )


def _string_override(
    metadata: Mapping[str, object],
    key: str,
) -> str | None:
    if key not in metadata:
        return None
    value = metadata[key]
    if not isinstance(value, str) or not value.strip():
        raise HardwareAnalysisError(f"metadata {key} must be a non-empty string")
    return value.strip()


def _canonical_list_override(
    metadata: Mapping[str, object],
    key: str,
    allowed: Mapping[str, str],
) -> list[str] | None:
    if key not in metadata:
        return None
    value = metadata[key]
    if not isinstance(value, list):
        raise HardwareAnalysisError(f"metadata {key} must be a list of strings")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise HardwareAnalysisError(f"metadata {key} must be a list of strings")
        canonical = allowed.get(item.strip().casefold())
        if canonical is None:
            raise HardwareAnalysisError(f"metadata {key} contains an unsupported value")
        normalized.append(canonical)
    return _deduplicate(normalized)


def _constraints_override(
    metadata: Mapping[str, object],
) -> list[str] | None:
    if "constraints" not in metadata:
        return None
    value = metadata["constraints"]
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise HardwareAnalysisError("metadata constraints must be a list of strings")
    return _deduplicate([item.strip() for item in value])


def _component_overrides(metadata: Mapping[str, object]) -> dict[str, str] | None:
    if "component_overrides" not in metadata:
        return None
    value = metadata["component_overrides"]
    if not isinstance(value, dict):
        raise HardwareAnalysisError("metadata component_overrides must be a mapping")
    normalized: dict[str, str] = {}
    for peripheral, component_name in value.items():
        if not isinstance(peripheral, str) or not isinstance(component_name, str):
            raise HardwareAnalysisError("component overrides must contain strings")
        canonical = _PERIPHERALS.get(peripheral.strip().casefold())
        if canonical is None or not component_name.strip():
            raise HardwareAnalysisError("component override is not supported")
        normalized[canonical] = component_name.strip()
    return normalized


class HardwareRequirementAnalyzer:
    def analyze(
        self,
        source: str | FirmwareProject,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> HardwareRequirement:
        if isinstance(source, FirmwareProject):
            base_metadata = dict(source.metadata)
            project_peripherals = base_metadata.get("peripherals", [])
            if not isinstance(project_peripherals, list) or any(
                not isinstance(item, str) or not item.strip()
                for item in project_peripherals
            ):
                raise HardwareAnalysisError(
                    "firmware project peripherals must be a list of strings"
                )
            requirement_text = " ".join(
                [
                    "Firmware project",
                    source.name,
                    source.platform,
                    *project_peripherals,
                ]
            )
            project_name = source.name
            detected_platform = _platform(source.platform)
            detected_mcu = _mcu(str(base_metadata.get("mcu", "")))
            if detected_mcu is None:
                detected_mcu = _mcu(source.platform) or detected_platform
            detected_peripherals = _peripherals(requirement_text)
        elif isinstance(source, str) and source.strip():
            base_metadata = {}
            requirement_text = source.strip()
            project_name = None
            detected_platform = _platform(requirement_text)
            detected_mcu = _mcu(requirement_text)
            detected_peripherals = _peripherals(requirement_text)
        else:
            raise HardwareAnalysisError("hardware requirement must not be empty")

        payload = {**base_metadata, **dict(metadata or {})}
        payload.pop("firmware_project", None)

        project_name_override = _string_override(payload, "project_name")
        platform_override = _string_override(payload, "platform")
        mcu_override = _string_override(payload, "mcu")
        if platform_override is not None:
            detected_platform = _platform(platform_override)
            if detected_platform is None:
                raise HardwareAnalysisError("metadata platform is not supported")
        if mcu_override is not None:
            detected_mcu = _mcu(mcu_override)
            if detected_mcu is None:
                raise HardwareAnalysisError("metadata mcu is not supported")
            if platform_override is None:
                detected_platform = _platform(mcu_override)

        if (
            detected_platform is not None
            and detected_mcu is not None
            and _platform(detected_mcu) != detected_platform
        ):
            raise HardwareAnalysisError("metadata platform and mcu do not match")

        peripheral_override = _canonical_list_override(
            payload, "peripherals", _PERIPHERALS
        )
        peripherals = (
            peripheral_override
            if peripheral_override is not None
            else detected_peripherals
        )
        interface_override = _canonical_list_override(
            payload, "interfaces", _INTERFACES
        )
        interfaces = (
            interface_override
            if interface_override is not None
            else _derived_interfaces(peripherals)
        )
        constraints = _constraints_override(payload) or []
        overrides = _component_overrides(payload)
        if overrides is not None:
            payload["component_overrides"] = overrides

        return HardwareRequirement(
            requirement=requirement_text,
            project_name=project_name_override or project_name,
            platform=detected_platform,
            mcu=detected_mcu,
            peripherals=peripherals,
            interfaces=interfaces,
            constraints=constraints,
            metadata=payload,
        )
