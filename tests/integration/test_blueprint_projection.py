from __future__ import annotations

from embedded_copilot.agents.types import AgentTask
from embedded_copilot.hardware.agent import HardwareAgent
from embedded_copilot.hardware_design.adapter import (
    HardwareBlueprintProjectionAgentAdapter,
)
from embedded_copilot.supervisor.agent import SupervisorAgent


def _task() -> AgentTask:
    return AgentTask(
        task_id="blueprint-integration",
        task_type="analysis",
        requirement="Plan an ESP32-S3 camera terminal.",
        metadata={
            "required_agents": ["hardware"],
            "platform": "ESP32",
            "mcu": "ESP32-S3",
            "peripherals": ["Camera"],
        },
    )


def test_supervisor_preserves_legacy_outputs_and_execution_evidence() -> None:
    legacy = SupervisorAgent(agents=(HardwareAgent(),)).run(_task())
    projected = SupervisorAgent(
        agents=(HardwareBlueprintProjectionAgentAdapter(HardwareAgent()),)
    ).run(_task())

    assert projected.metadata["supervisor_plan"] == legacy.metadata["supervisor_plan"]
    assert (
        projected.metadata["engineering_report"]
        == legacy.metadata["engineering_report"]
    )

    legacy_hardware = legacy.metadata["agent_results"][0]
    projected_hardware = projected.metadata["agent_results"][0]
    assert "hardware_design" not in legacy_hardware["metadata"]
    artifact = projected_hardware["metadata"].pop("hardware_design")
    assert artifact["schema_version"] == 1
    assert projected_hardware == legacy_hardware


def test_artifact_is_not_exposed_by_engineering_report() -> None:
    result = SupervisorAgent(
        agents=(HardwareBlueprintProjectionAgentAdapter(HardwareAgent()),)
    ).run(_task())

    assert "hardware_design" not in result.metadata["engineering_report"]
    assert "hardware_design" in result.metadata["agent_results"][0]["metadata"]
