from __future__ import annotations

import re
from collections.abc import Callable, Mapping

from pydantic import Field, field_validator

from embedded_copilot.firmware.exceptions import FirmwareAnalysisError
from embedded_copilot.schemas.result import ContractModel


class FirmwareRequirementAnalysis(ContractModel):
    requirement: str = Field(min_length=1)
    platform: str | None = Field(default=None, min_length=1)
    framework: str | None = Field(default=None, min_length=1)
    features: list[str] = Field(default_factory=list)
    peripherals: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("requirement", "platform", "framework", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


_FEATURE_RULES: tuple[tuple[str, str], ...] = (
    ("sensor", r"温湿度|传感器|sensor"),
    ("wifi", r"wifi"),
    ("camera", r"camera|相机|摄像头"),
    ("freertos", r"freertos"),
    ("gpio", r"gpio"),
    ("uart", r"uart"),
    ("spi", r"spi"),
    ("adc", r"adc"),
)
_PERIPHERAL_BY_FEATURE = {
    "sensor": "GPIO",
    "wifi": "WiFi",
    "camera": "Camera",
    "gpio": "GPIO",
    "uart": "UART",
    "spi": "SPI",
    "adc": "ADC",
}
_FEATURE_VALUES = {value: value for value, _ in _FEATURE_RULES}
_PERIPHERAL_VALUES = {
    value.casefold(): value for value in _PERIPHERAL_BY_FEATURE.values()
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
    if re.search(r"esp32(?:[-_]?[a-z0-9]+)?", text, re.IGNORECASE):
        return "ESP32"
    if re.search(r"stm32[a-z0-9]*", text, re.IGNORECASE):
        return "STM32"
    return None


def _framework(text: str) -> str | None:
    candidates = (
        ("ESP-IDF", r"esp[-_ ]?idf"),
        ("FreeRTOS", r"freertos"),
        ("HAL", r"(?<![A-Za-z0-9])hal(?![A-Za-z0-9])"),
    )
    matches: list[tuple[int, str]] = []
    for value, pattern in candidates:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is not None:
            matches.append((match.start(), value))
    return min(matches)[1] if matches else None


def _features(text: str) -> list[str]:
    matches: list[tuple[int, str]] = []
    for value, pattern in _FEATURE_RULES:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is not None:
            matches.append((match.start(), value))
    return _deduplicate([value for _, value in sorted(matches)])


def _normalized_string_override(
    metadata: Mapping[str, object],
    key: str,
    normalizer: Callable[[str], str | None],
) -> str | None:
    if key not in metadata:
        return None
    value = metadata[key]
    if not isinstance(value, str) or not value.strip():
        raise FirmwareAnalysisError(f"metadata {key} must be a non-empty string")
    normalized = normalizer(value.strip())
    if normalized is None:
        raise FirmwareAnalysisError(f"metadata {key} is not supported")
    return normalized


def _list_override(
    metadata: Mapping[str, object],
    key: str,
    allowed_values: Mapping[str, str],
) -> list[str] | None:
    if key not in metadata:
        return None
    value = metadata[key]
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise FirmwareAnalysisError(f"metadata {key} must be a list of strings")
    normalized: list[str] = []
    for item in value:
        canonical = allowed_values.get(item.strip().casefold())
        if canonical is None:
            raise FirmwareAnalysisError(f"metadata {key} contains an unsupported value")
        normalized.append(canonical)
    return _deduplicate(normalized)


class FirmwareRequirementAnalyzer:
    def analyze(
        self,
        requirement: str,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> FirmwareRequirementAnalysis:
        normalized_requirement = requirement.strip()
        if not normalized_requirement:
            raise FirmwareAnalysisError("firmware requirement must not be empty")
        payload = dict(metadata or {})
        detected_features = _features(normalized_requirement)
        feature_override = _list_override(payload, "features", _FEATURE_VALUES)
        peripheral_override = _list_override(
            payload,
            "peripherals",
            _PERIPHERAL_VALUES,
        )
        features = feature_override if feature_override is not None else detected_features
        peripherals = (
            peripheral_override
            if peripheral_override is not None
            else _deduplicate(
                [
                    _PERIPHERAL_BY_FEATURE[feature]
                    for feature in features
                    if feature in _PERIPHERAL_BY_FEATURE
                ]
            )
        )
        return FirmwareRequirementAnalysis(
            requirement=normalized_requirement,
            platform=_normalized_string_override(payload, "platform", _platform)
            or _platform(normalized_requirement),
            framework=_normalized_string_override(payload, "framework", _framework)
            or _framework(normalized_requirement),
            features=features,
            peripherals=peripherals,
            metadata=payload,
        )
