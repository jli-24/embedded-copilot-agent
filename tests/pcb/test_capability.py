from dataclasses import FrozenInstanceError

import pytest

from embedded_copilot.agents.registry import AgentRegistry
from embedded_copilot.core.capability import CapabilityRegistry
from embedded_copilot.pcb.agent import PCBAgent
from embedded_copilot.pcb.capability import (
    PCBCapability,
    PCBCapabilityDescriptor,
    register_pcb_foundation,
)


def test_pcb_capability_descriptor_and_explicit_registration() -> None:
    descriptor = PCBCapabilityDescriptor()
    agent_registry = AgentRegistry()
    capability_registry = CapabilityRegistry()

    agent = register_pcb_foundation(
        agent_registry,
        capability_registry,
        capability=descriptor,
    )

    assert isinstance(descriptor, PCBCapability)
    assert descriptor.name == "pcb"
    assert descriptor.agent_name == "PCBAgent"
    assert descriptor.supported_inputs == ("HardwarePlan", "description")
    assert agent_registry.get_agent("PCBAgent") is agent
    assert capability_registry.get("pcb") is descriptor
    with pytest.raises(FrozenInstanceError):
        descriptor.name = "changed"


def test_pcb_registration_rejects_duplicates_without_partial_write() -> None:
    agent_registry = AgentRegistry()
    capability_registry = CapabilityRegistry()
    capability_registry.register("pcb", object())

    with pytest.raises(ValueError, match="already registered"):
        register_pcb_foundation(agent_registry, capability_registry)

    assert agent_registry.list_agents() == []
    assert capability_registry.list_capabilities() == ["pcb"]


def test_pcb_registration_prevalidates_empty_names() -> None:
    agent_registry = AgentRegistry()
    capability_registry = CapabilityRegistry()

    with pytest.raises(ValueError, match="must not be empty"):
        register_pcb_foundation(
            agent_registry,
            capability_registry,
            agent=PCBAgent(),
            capability=PCBCapabilityDescriptor(name=" "),
        )

    assert agent_registry.list_agents() == []
    assert capability_registry.list_capabilities() == []
