from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.firmware.models import FirmwareRequest, ValidationResult


@runtime_checkable
class FirmwarePlatform(Protocol):
    name: str

    def supported_features(self) -> tuple[str, ...]: ...

    def validate_request(self, request: FirmwareRequest) -> ValidationResult: ...


def _validate_request(
    request: FirmwareRequest,
    *,
    platform_name: str,
    frameworks: tuple[str, ...],
    peripherals: tuple[str, ...],
) -> ValidationResult:
    supported_frameworks = {feature.casefold() for feature in frameworks}
    supported_peripherals = {feature.casefold() for feature in peripherals}
    errors: list[str] = []
    if request.platform.casefold() != platform_name.casefold():
        errors.append(f"platform must be {platform_name}")
    if (
        request.framework is not None
        and request.framework.casefold() not in supported_frameworks
    ):
        errors.append(f"unsupported framework: {request.framework}")
    for peripheral in request.peripherals:
        if peripheral.casefold() not in supported_peripherals:
            errors.append(f"unsupported peripheral: {peripheral}")
    return ValidationResult(success=not errors, errors=errors)


class ESP32Platform:
    name = "ESP32"
    _FRAMEWORKS = ("ESP-IDF", "FreeRTOS")
    _PERIPHERALS = ("GPIO", "WiFi", "SPI", "Camera")
    _FEATURES = (name, *_FRAMEWORKS, *_PERIPHERALS)

    def supported_features(self) -> tuple[str, ...]:
        return self._FEATURES

    def validate_request(self, request: FirmwareRequest) -> ValidationResult:
        return _validate_request(
            request,
            platform_name=self.name,
            frameworks=self._FRAMEWORKS,
            peripherals=self._PERIPHERALS,
        )


class STM32Platform:
    name = "STM32"
    _FRAMEWORKS = ("HAL",)
    _PERIPHERALS = ("UART", "SPI", "ADC")
    _FEATURES = (name, *_FRAMEWORKS, *_PERIPHERALS)

    def supported_features(self) -> tuple[str, ...]:
        return self._FEATURES

    def validate_request(self, request: FirmwareRequest) -> ValidationResult:
        return _validate_request(
            request,
            platform_name=self.name,
            frameworks=self._FRAMEWORKS,
            peripherals=self._PERIPHERALS,
        )
