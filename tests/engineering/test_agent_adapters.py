from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.engineering.agent_adapters import (
    ExtensionMetadataSanitizingAgentAdapter,
    FirmwareAgentInputAdapter,
    HardwareAgentInputAdapter,
)
from embedded_copilot.engineering.models import RealEngineeringEnvelope
from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.models import HardwareComponent, HardwarePlan

from tests.engineering.fixtures import datasheet_model, firmware_review


class _RecordingAgent(BaseAgent):
    description = "recording"
    capabilities = ("recording",)

    def __init__(self, name: str, result: AgentResult) -> None:
        self.name = name
        self.result = result
        self.tasks: list[AgentTask] = []

    def run(self, task: AgentTask) -> AgentResult:
        self.tasks.append(task)
        return self.result


def _task(envelope: RealEngineeringEnvelope) -> AgentTask:
    return AgentTask(
        task_id="real-input",
        task_type="review",
        requirement="Analyze ESP32-S3 firmware and Datasheet",
        metadata={
            "public": "keep",
            "_real_engineering_input": envelope.model_dump(mode="json"),
        },
    )


def test_firmware_agent_adapter_projects_review_without_calling_domain_agent() -> None:
    delegate = _RecordingAgent(
        "FirmwareAgent",
        AgentResult(
            agent_name="FirmwareAgent",
            status=AgentStatus.ERROR,
            output="must not run",
        ),
    )
    result = FirmwareAgentInputAdapter(delegate).run(
        _task(RealEngineeringEnvelope(firmware_review=firmware_review()))
    )

    project = FirmwareProject.model_validate_json(result.output)
    assert result.status is AgentStatus.SUCCESS
    assert delegate.tasks == []
    assert project.metadata["analysis_mode"] == "deterministic_static_review"


def test_hardware_agent_adapter_sanitizes_input_and_projects_crosscheck() -> None:
    plan = HardwarePlan(
        project_name="review",
        platform="ESP32",
        mcu="ESP32-S3",
        components=(
            HardwareComponent(
                name="Power regulation stage",
                category="power",
                description="Unverified power stage.",
            ),
        ),
        rationale="Legacy deterministic plan.",
    )
    delegate = _RecordingAgent(
        "HardwareAgent",
        AgentResult(
            agent_name="HardwareAgent",
            status=AgentStatus.SUCCESS,
            output=plan.model_dump_json(),
        ),
    )
    envelope = RealEngineeringEnvelope(
        datasheet=datasheet_model(),
        firmware_review=firmware_review(),
    )

    result = HardwareAgentInputAdapter(delegate).run(_task(envelope))

    assert len(delegate.tasks) == 1
    delegated = delegate.tasks[0]
    serialized_task = delegated.model_dump_json()
    assert "_real_engineering_input" not in delegated.metadata
    assert "UnifiedDatasheetModel" not in serialized_task
    assert "FirmwareReviewResult" not in serialized_task
    assert "knowledge_documents" in delegated.metadata
    projected = HardwarePlan.model_validate_json(result.output)
    assert any("[HIGH] datasheet-firmware-gpio-conflict" in item for item in projected.constraints)
    assert "SPI" in projected.interfaces


def test_non_extension_agent_adapter_only_strips_private_metadata() -> None:
    expected = AgentResult(
        agent_name="DebugAgent",
        status=AgentStatus.SUCCESS,
        output="delegated",
    )
    delegate = _RecordingAgent("DebugAgent", expected)
    original = _task(RealEngineeringEnvelope(firmware_review=firmware_review()))
    before = original.model_dump_json()

    result = ExtensionMetadataSanitizingAgentAdapter(delegate).run(original)

    assert result is expected
    assert len(delegate.tasks) == 1
    assert delegate.tasks[0].metadata == {"public": "keep"}
    assert original.model_dump_json() == before


def test_agent_adapter_revalidates_constructed_envelope_instance() -> None:
    delegate = _RecordingAgent(
        "FirmwareAgent",
        AgentResult(
            agent_name="FirmwareAgent",
            status=AgentStatus.SUCCESS,
            output="delegated",
        ),
    )
    invalid = RealEngineeringEnvelope.model_construct(schema_version=2)
    task = AgentTask(
        task_id="invalid-envelope",
        task_type="review",
        requirement="Review firmware",
        metadata={"_real_engineering_input": invalid},
    )

    with pytest.raises(ValidationError):
        FirmwareAgentInputAdapter(delegate).run(task)

    assert delegate.tasks == []
