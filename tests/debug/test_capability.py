from dataclasses import FrozenInstanceError

import pytest

from embedded_copilot.agents.registry import AgentRegistry
from embedded_copilot.core.capability import CapabilityRegistry
from embedded_copilot.debug.capability import (
    DebugCapability,
    DebugCapabilityDescriptor,
    register_debug_foundation,
)


def test_debug_capability_descriptor_and_explicit_registration() -> None:
    descriptor = DebugCapabilityDescriptor()
    agent_registry = AgentRegistry()
    capability_registry = CapabilityRegistry()

    agent = register_debug_foundation(
        agent_registry,
        capability_registry,
        capability=descriptor,
    )

    assert isinstance(descriptor, DebugCapability)
    assert descriptor.name == "debug"
    assert descriptor.agent_name == "DebugAgent"
    assert descriptor.supported_platforms == ("ESP32", "STM32")
    assert agent_registry.get_agent("DebugAgent") is agent
    assert capability_registry.get("debug") is descriptor
    with pytest.raises(FrozenInstanceError):
        descriptor.name = "changed"  # type: ignore[misc]


def test_debug_registration_rejects_conflict_without_partial_write() -> None:
    agent_registry = AgentRegistry()
    capability_registry = CapabilityRegistry()
    capability_registry.register("debug", object())

    with pytest.raises(ValueError, match="already registered"):
        register_debug_foundation(agent_registry, capability_registry)

    assert agent_registry.list_agents() == []
    assert capability_registry.list_capabilities() == ["debug"]


def test_debug_registration_rolls_back_when_second_write_fails() -> None:
    class FailingAgentRegistry(AgentRegistry):
        def register_agent(self, agent: object) -> None:  # type: ignore[override]
            raise RuntimeError("second write failed")

    agent_registry = FailingAgentRegistry()
    capability_registry = CapabilityRegistry()

    with pytest.raises(RuntimeError, match="second write failed"):
        register_debug_foundation(agent_registry, capability_registry)

    assert capability_registry.list_capabilities() == []


def test_debug_registration_prevalidates_names() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        register_debug_foundation(
            AgentRegistry(),
            CapabilityRegistry(),
            capability=DebugCapabilityDescriptor(name=" "),
        )
