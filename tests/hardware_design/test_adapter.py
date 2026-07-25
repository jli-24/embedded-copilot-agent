from __future__ import annotations

import pytest

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.engineering.models import RealEngineeringEnvelope
from embedded_copilot.hardware.models import HardwareComponent, HardwarePlan
from embedded_copilot.hardware_design.adapter import (
    HardwareBlueprintProjectionAgentAdapter,
)

from tests.engineering.fixtures import datasheet_model, firmware_review


def _plan() -> HardwarePlan:
    return HardwarePlan(
        project_name="security-terminal",
        platform="ESP32",
        mcu="ESP32-S3",
        components=[
            HardwareComponent(
                name="PIR",
                category="sensor",
                interface=["GPIO"],
                description="PIR observation from HardwarePlan.",
            )
        ],
        interfaces=["GPIO"],
        power_requirements=[],
        constraints=[],
        rationale="Unverified plan.",
    )


class _Delegate(BaseAgent):
    name = "HardwareAgent"
    description = "test delegate"
    capabilities = ("hardware_analysis",)

    def __init__(self, result: AgentResult) -> None:
        self.result = result
        self.tasks: list[AgentTask] = []

    def run(self, task: AgentTask) -> AgentResult:
        self.tasks.append(task.model_copy(deep=True))
        return self.result


class _RaisingDelegate(_Delegate):
    def run(self, task: AgentTask) -> AgentResult:
        raise RuntimeError("delegate failure")


def _success_result() -> AgentResult:
    plan = _plan()
    return AgentResult(
        agent_name="HardwareAgent",
        status=AgentStatus.SUCCESS,
        output=plan.model_dump_json(),
        metadata={"hardware_plan": plan.model_dump(mode="json"), "legacy": "keep"},
    )


def _task(envelope: RealEngineeringEnvelope | None = None) -> AgentTask:
    metadata: dict[str, object] = {"public": "keep"}
    if envelope is not None:
        metadata["_real_engineering_input"] = envelope.model_dump(mode="python")
    return AgentTask(
        task_id="task-1",
        task_type="hardware",
        requirement="Explain the existing hardware plan.",
        metadata=metadata,
    )


def test_adapter_adds_optional_artifact_without_changing_delegate_result() -> None:
    delegated = _success_result()
    delegate = _Delegate(delegated)
    adapter = HardwareBlueprintProjectionAgentAdapter(delegate)
    task = _task()
    before = task.model_dump(mode="python")

    result = adapter.run(task)

    assert result.agent_name == delegated.agent_name
    assert result.status is delegated.status
    assert result.output == delegated.output
    assert result.metadata["hardware_plan"] == delegated.metadata["hardware_plan"]
    assert result.metadata["legacy"] == "keep"
    assert result.metadata["hardware_design"]["schema_version"] == 1
    assert result.metadata["hardware_design"]["approval"] == {
        "status": "PROPOSED",
        "revision": 1,
        "feedback_summary": None,
    }
    assert task.model_dump(mode="python") == before


def test_adapter_uses_copied_envelope_for_projection() -> None:
    envelope = RealEngineeringEnvelope(
        datasheet=datasheet_model(),
        firmware_review=firmware_review(),
    )
    task = _task(envelope)
    before = task.model_dump(mode="python")
    adapter = HardwareBlueprintProjectionAgentAdapter(_Delegate(_success_result()))

    result = adapter.run(task)

    gpio = result.metadata["hardware_design"]["blueprint"]["gpio_assignments"]
    assert gpio[0]["status"] == "conflict"
    assert task.model_dump(mode="python") == before


def test_adapter_preserves_error_result_without_requiring_artifact() -> None:
    delegated = AgentResult(
        agent_name="HardwareAgent",
        status=AgentStatus.ERROR,
        output="hardware planning failed",
        metadata={"error_type": "HardwarePlanningError"},
    )
    adapter = HardwareBlueprintProjectionAgentAdapter(_Delegate(delegated))

    result = adapter.run(_task())

    assert result == delegated
    assert "hardware_design" not in result.metadata
    assert "hardware_design_error" not in result.metadata


def test_adapter_does_not_swallow_delegate_exceptions() -> None:
    adapter = HardwareBlueprintProjectionAgentAdapter(
        _RaisingDelegate(_success_result())
    )

    with pytest.raises(RuntimeError, match="delegate failure"):
        adapter.run(_task())


def test_adapter_projection_failure_is_redacted_and_fail_open(monkeypatch) -> None:
    delegated = _success_result()
    adapter = HardwareBlueprintProjectionAgentAdapter(_Delegate(delegated))

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError(r"secret source at C:\Users\private\main.c")

    monkeypatch.setattr(
        "embedded_copilot.hardware_design.adapter.project_artifact",
        fail,
    )

    result = adapter.run(_task())

    assert result.output == delegated.output
    assert result.status is delegated.status
    assert result.metadata["legacy"] == "keep"
    assert result.metadata["hardware_design_error"] == {"code": "projection_failed"}
    assert "hardware_design" not in result.metadata
    assert "private" not in result.model_dump_json()
