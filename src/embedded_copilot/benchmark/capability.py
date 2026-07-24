from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from embedded_copilot.benchmark.runner import BenchmarkRunner
from embedded_copilot.core.capability import CapabilityRegistry


@runtime_checkable
class BenchmarkCapability(Protocol):
    name: str
    description: str
    agent_name: str
    supported_targets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkCapabilityDescriptor:
    name: str = "benchmark"
    description: str = "Deterministic offline Foundation benchmark evaluation."
    agent_name: str = "BenchmarkRunner"
    supported_targets: tuple[str, ...] = (
        "SupervisorAgent",
        "FirmwareAgent",
        "HardwareAgent",
        "PCBAgent",
        "DebugAgent",
    )


def register_benchmark_foundation(
    capability_registry: CapabilityRegistry,
    *,
    runner: BenchmarkRunner,
    capability: BenchmarkCapability | None = None,
) -> BenchmarkRunner:
    active_capability = (
        capability if capability is not None else BenchmarkCapabilityDescriptor()
    )
    capability_name = active_capability.name.strip()
    if not capability_name:
        raise ValueError("capability name must not be empty")
    if capability_name in capability_registry.list_capabilities():
        raise ValueError(f"capability already registered: {capability_name}")
    capability_registry.register(capability_name, active_capability)
    return runner
