from dataclasses import FrozenInstanceError

import pytest

from embedded_copilot.agents.registry import AgentRegistry
from embedded_copilot.core.capability import CapabilityRegistry
from embedded_copilot.supervisor.agent import SupervisorAgent
from embedded_copilot.supervisor.capability import (
    SupervisorCapability,
    SupervisorCapabilityDescriptor,
    register_supervisor_foundation,
)


def test_supervisor_capability_descriptor_and_explicit_registration() -> None:
    descriptor = SupervisorCapabilityDescriptor()
    agent_registry = AgentRegistry()
    capability_registry = CapabilityRegistry()

    agent = register_supervisor_foundation(
        agent_registry,
        capability_registry,
        capability=descriptor,
    )

    assert isinstance(descriptor, SupervisorCapability)
    assert descriptor.name == "supervisor"
    assert descriptor.agent_name == "SupervisorAgent"
    assert descriptor.supported_agents == (
        "FirmwareAgent",
        "HardwareAgent",
        "PCBAgent",
        "DebugAgent",
    )
    assert agent_registry.get_agent("SupervisorAgent") is agent
    assert capability_registry.get("supervisor") is descriptor
    with pytest.raises(FrozenInstanceError):
        descriptor.name = "changed"  # type: ignore[misc]


def test_supervisor_registration_rejects_conflict_without_partial_write() -> None:
    agent_registry = AgentRegistry()
    capability_registry = CapabilityRegistry()
    capability_registry.register("supervisor", object())

    with pytest.raises(ValueError, match="already registered"):
        register_supervisor_foundation(agent_registry, capability_registry)

    assert agent_registry.list_agents() == []
    assert capability_registry.list_capabilities() == ["supervisor"]


def test_supervisor_registration_prevalidates_all_names() -> None:
    agent_registry = AgentRegistry()
    capability_registry = CapabilityRegistry()

    with pytest.raises(ValueError, match="must not be empty"):
        register_supervisor_foundation(
            agent_registry,
            capability_registry,
            agent=SupervisorAgent(),
            capability=SupervisorCapabilityDescriptor(name=" "),
        )

    assert agent_registry.list_agents() == []
    assert capability_registry.list_capabilities() == []


def test_supervisor_registration_rolls_back_when_second_write_fails() -> None:
    class FailingAgentRegistry(AgentRegistry):
        def register_agent(self, agent: object) -> None:  # type: ignore[override]
            raise RuntimeError("second registry write failed")

    agent_registry = FailingAgentRegistry()
    capability_registry = CapabilityRegistry()

    with pytest.raises(RuntimeError, match="second registry write failed"):
        register_supervisor_foundation(agent_registry, capability_registry)

    assert agent_registry.list_agents() == []
    assert capability_registry.list_capabilities() == []


def test_supervisor_registration_has_no_partial_write_when_capability_write_fails() -> None:
    class FailingCapabilityRegistry(CapabilityRegistry):
        def register(self, name: str, capability: object) -> None:
            raise RuntimeError("capability registry write failed")

    agent_registry = AgentRegistry()
    capability_registry = FailingCapabilityRegistry()

    with pytest.raises(RuntimeError, match="capability registry write failed"):
        register_supervisor_foundation(agent_registry, capability_registry)

    assert agent_registry.list_agents() == []
    assert capability_registry.list_capabilities() == []
