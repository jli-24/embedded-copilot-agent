"""Narrow facade for Hardware Validation."""

from __future__ import annotations

from embedded_copilot.engineering_validation.contracts import HardwareValidationPort


class HardwareValidationRuntime:
    __slots__ = ("__port",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use create_hardware_validation_runtime")

    @classmethod
    def _compose(cls, port: HardwareValidationPort) -> HardwareValidationRuntime:
        runtime = object.__new__(cls)
        runtime.__port = port
        return runtime

    def hardware_validation_port(self) -> HardwareValidationPort:
        return self.__port
