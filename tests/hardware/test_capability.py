import importlib.util

import pytest

from embedded_copilot.agents.registry import AgentRegistry
from embedded_copilot.core.capability import CapabilityRegistry
from embedded_copilot.hardware import HardwareAgent as PublicHardwareAgent
from embedded_copilot.hardware.agent import HardwareAgent
from embedded_copilot.hardware.capability import (
    HardwareCapability,
    HardwareCapabilityDescriptor,
    register_hardware_foundation,
)


def test_hardware_agent_public_path_does_not_create_runtime_agent() -> None:
    assert PublicHardwareAgent is HardwareAgent
    assert importlib.util.find_spec("embedded_copilot.agents.hardware") is None


def test_hardware_capability_descriptor_and_explicit_registration() -> None:
    descriptor = HardwareCapabilityDescriptor()
    agent_registry = AgentRegistry()
    capability_registry = CapabilityRegistry()

    agent = register_hardware_foundation(
        agent_registry,
        capability_registry,
        capability=descriptor,
    )

    assert isinstance(descriptor, HardwareCapability)
    assert descriptor.name == "hardware"
    assert descriptor.supported_platforms == ("ESP32", "STM32")
    assert agent_registry.get_agent("HardwareAgent") is agent
    assert capability_registry.get("hardware") is descriptor


def test_hardware_registration_rejects_duplicates_without_partial_write() -> None:
    agent_registry = AgentRegistry()
    capability_registry = CapabilityRegistry()
    capability_registry.register("hardware", object())

    with pytest.raises(ValueError, match="already registered"):
        register_hardware_foundation(agent_registry, capability_registry)

    assert agent_registry.list_agents() == []
    assert capability_registry.list_capabilities() == ["hardware"]


def test_hardware_registration_normalizes_names_before_duplicate_check() -> None:
    agent_registry = AgentRegistry()
    capability_registry = CapabilityRegistry()
    capability_registry.register("hardware", object())

    with pytest.raises(ValueError, match="already registered"):
        register_hardware_foundation(
            agent_registry,
            capability_registry,
            capability=HardwareCapabilityDescriptor(name=" hardware "),
        )

    assert agent_registry.list_agents() == []
