"""Composition root for deterministic Firmware Engineering."""

from embedded_copilot.engineering_firmware.facade import EngineeringFirmwareRuntime
from embedded_copilot.engineering_firmware.runtime import _FirmwareEngineeringAgent


def create_engineering_firmware_runtime() -> EngineeringFirmwareRuntime:
    return EngineeringFirmwareRuntime._compose(_FirmwareEngineeringAgent())
