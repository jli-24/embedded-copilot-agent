import inspect

import pytest

from embedded_copilot.agents.firmware import FirmwareAgent as RuntimeFirmwareAgent
from embedded_copilot.agents.registry import AgentRegistry
from embedded_copilot.agents.types import AgentStatus, AgentTask
from embedded_copilot.core.capability import CapabilityRegistry
from embedded_copilot.firmware import FirmwareAgent as PublicFoundationAgent
from embedded_copilot.firmware.agent import FirmwareAgent as FoundationFirmwareAgent
from embedded_copilot.firmware.capability import (
    FirmwareCapability,
    FirmwareCapabilityDescriptor,
    register_firmware_foundation,
)
from embedded_copilot.firmware.models import GeneratedCode


def test_firmware_agent_import_paths_do_not_shadow_runtime_agent() -> None:
    assert PublicFoundationAgent is FoundationFirmwareAgent
    assert FoundationFirmwareAgent is not RuntimeFirmwareAgent
    assert inspect.iscoroutinefunction(RuntimeFirmwareAgent.run)
    assert not inspect.iscoroutinefunction(FoundationFirmwareAgent.run)


def test_firmware_agent_extracts_request_and_returns_generated_json() -> None:
    result = FoundationFirmwareAgent().run(
        AgentTask(
            task_id="1",
            task_type="firmware",
            requirement="ESP32 ESP-IDF GPIO WiFi sensor",
        )
    )

    generated = GeneratedCode.model_validate_json(result.output)
    assert result.status is AgentStatus.SUCCESS
    assert generated.platform == "ESP32"
    assert [file.filename for file in generated.files] == ["main.c", "wifi.c"]
    assert result.metadata["validation"]["success"] is True


def test_firmware_agent_metadata_overrides_rule_extraction() -> None:
    result = FoundationFirmwareAgent().run(
        AgentTask(
            task_id="2",
            task_type="firmware",
            requirement="create serial firmware",
            metadata={
                "platform": "STM32",
                "framework": "HAL",
                "peripherals": ["UART"],
                "project_name": "serial_demo",
            },
        )
    )

    generated = GeneratedCode.model_validate_json(result.output)
    assert generated.project_name == "serial_demo"
    assert generated.platform == "STM32"


def test_firmware_agent_reports_missing_platform() -> None:
    result = FoundationFirmwareAgent().run(
        AgentTask(task_id="3", task_type="firmware", requirement="GPIO example")
    )

    assert result.status is AgentStatus.ERROR
    assert "platform" in result.output.lower()


def test_firmware_agent_maps_generation_error() -> None:
    result = FoundationFirmwareAgent().run(
        AgentTask(
            task_id="4",
            task_type="firmware",
            requirement="ESP32 SPI mock",
        )
    )

    assert result.status is AgentStatus.ERROR
    assert result.metadata["error_type"] == "FirmwareGenerationError"


def test_capability_descriptor_and_explicit_bootstrap() -> None:
    descriptor = FirmwareCapabilityDescriptor()
    agent_registry = AgentRegistry()
    capability_registry = CapabilityRegistry()

    agent = register_firmware_foundation(
        agent_registry,
        capability_registry,
        capability=descriptor,
    )

    assert isinstance(descriptor, FirmwareCapability)
    assert descriptor.supported_platforms == ("ESP32", "STM32")
    assert agent_registry.get_agent("FirmwareAgent") is agent
    assert capability_registry.get("firmware") is descriptor


def test_bootstrap_rejects_duplicates_without_partial_registration() -> None:
    agent_registry = AgentRegistry()
    capability_registry = CapabilityRegistry()
    capability_registry.register("firmware", object())

    with pytest.raises(ValueError, match="already registered"):
        register_firmware_foundation(agent_registry, capability_registry)

    assert agent_registry.list_agents() == []
    assert capability_registry.list_capabilities() == ["firmware"]


def test_bootstrap_normalizes_names_before_duplicate_check() -> None:
    agent_registry = AgentRegistry()
    capability_registry = CapabilityRegistry()
    capability_registry.register("firmware", object())

    with pytest.raises(ValueError, match="already registered"):
        register_firmware_foundation(
            agent_registry,
            capability_registry,
            capability=FirmwareCapabilityDescriptor(name=" firmware "),
        )

    assert agent_registry.list_agents() == []
