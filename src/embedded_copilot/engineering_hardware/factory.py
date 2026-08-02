"""Composition root for deterministic Hardware Engineering."""

from embedded_copilot.engineering_hardware.facade import EngineeringHardwareRuntime
from embedded_copilot.engineering_hardware.runtime import _HardwareEngineeringAgent


def create_engineering_hardware_runtime() -> EngineeringHardwareRuntime:
    return EngineeringHardwareRuntime._compose(_HardwareEngineeringAgent())
