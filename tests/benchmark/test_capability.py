from __future__ import annotations

import pytest

from embedded_copilot.benchmark.capability import (
    BenchmarkCapability,
    BenchmarkCapabilityDescriptor,
    register_benchmark_foundation,
)
from embedded_copilot.benchmark.runner import BenchmarkRunner
from embedded_copilot.core.capability import CapabilityRegistry


def test_benchmark_capability_descriptor_is_runtime_checkable_and_fixed() -> None:
    descriptor = BenchmarkCapabilityDescriptor()

    assert isinstance(descriptor, BenchmarkCapability)
    assert descriptor.name == "benchmark"
    assert descriptor.agent_name == "BenchmarkRunner"
    assert descriptor.supported_targets == (
        "SupervisorAgent",
        "FirmwareAgent",
        "HardwareAgent",
        "PCBAgent",
        "DebugAgent",
    )


def test_registration_only_writes_explicit_capability_registry() -> None:
    registry = CapabilityRegistry()
    runner = BenchmarkRunner({})

    returned = register_benchmark_foundation(registry, runner=runner)

    assert returned is runner
    assert registry.list_capabilities() == ["benchmark"]
    assert isinstance(registry.get("benchmark"), BenchmarkCapabilityDescriptor)


def test_registration_prevalidates_conflict_and_blank_name() -> None:
    registry = CapabilityRegistry()
    runner = BenchmarkRunner({})
    registry.register("benchmark", object())

    with pytest.raises(ValueError, match="already registered"):
        register_benchmark_foundation(registry, runner=runner)
    assert registry.list_capabilities() == ["benchmark"]

    with pytest.raises(ValueError, match="must not be empty"):
        register_benchmark_foundation(
            CapabilityRegistry(),
            runner=runner,
            capability=BenchmarkCapabilityDescriptor(name=" "),
        )
