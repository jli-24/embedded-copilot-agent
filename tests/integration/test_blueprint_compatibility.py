from __future__ import annotations

from embedded_copilot.agents.types import AgentResult, AgentStatus
from embedded_copilot.api.models import AnalyzeRequest, AnalyzeResponse
from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.integration.executor import AgentExecutor
from embedded_copilot.integration.report import EngineeringReport


def _legacy_plan() -> HardwarePlan:
    return HardwarePlan(
        project_name="legacy",
        platform="ESP32",
        mcu="ESP32-S3",
        components=[],
        interfaces=[],
        power_requirements=[],
        constraints=[],
        rationale="Legacy unverified plan.",
    )


def test_public_contract_fields_do_not_expose_hardware_design_artifact() -> None:
    assert set(HardwarePlan.model_fields) == {
        "project_name",
        "platform",
        "mcu",
        "components",
        "interfaces",
        "power_requirements",
        "constraints",
        "rationale",
        "metadata",
    }
    assert set(AgentResult.model_fields) == {
        "agent_name",
        "status",
        "output",
        "metadata",
    }
    assert set(AnalyzeRequest.model_fields) == {
        "request",
        "attachments",
        "options",
    }
    assert set(AnalyzeResponse.model_fields) == {"execution_id", "status"}
    assert set(EngineeringReport.model_fields) == {
        "summary",
        "hardware_section",
        "firmware_section",
        "pcb_section",
        "debug_section",
        "recommendations",
        "trace",
    }


def test_execution_boundary_accepts_legacy_result_without_artifact() -> None:
    plan = _legacy_plan()
    legacy = AgentResult(
        agent_name="HardwareAgent",
        status=AgentStatus.SUCCESS,
        output=plan.model_dump_json(),
        metadata={"hardware_plan": plan.model_dump(mode="json")},
    )

    projected = AgentExecutor._validate_result(legacy)

    assert projected.status is AgentStatus.SUCCESS
    assert projected.result is not None
    assert projected.result.kind == "hardware"
    assert "hardware_design" not in legacy.metadata
