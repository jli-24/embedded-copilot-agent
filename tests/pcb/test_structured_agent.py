from __future__ import annotations

import inspect

from embedded_copilot.agents.types import AgentStatus, AgentTask
from embedded_copilot.pcb.adapters import attach_pcb_model
from embedded_copilot.pcb.agent import PCBAgent
from embedded_copilot.pcb.models import PCBReviewReport, UnifiedPCBModel


def _model(*, floating: bool = False) -> UnifiedPCBModel:
    return UnifiedPCBModel(
        board_name="esp32_board",
        source_format="kicad_pcb",
        components=(
            {
                "reference": "U1",
                "value": "ESP32-S3",
                "footprint": "QFN-56",
                "library": "Package_DFN_QFN",
                "position": {"x_mm": 10.0, "y_mm": 20.0},
                "layer": "F.Cu",
                "pins": (
                    {"number": "1", "pad_type": "smd", "net_name": "GND"},
                    {
                        "number": "2",
                        "pad_type": "smd",
                        "net_name": None if floating else "+3V3",
                    },
                ),
            },
        ),
        nets=(
            {"name": "GND", "net_type": "ground", "nodes": ()},
            {"name": "+3V3", "net_type": "power", "nodes": ()},
        ),
        layers=({"name": "F.Cu", "index": 0, "type": "signal"},),
    )


def test_agent_structured_path_returns_existing_report_schema() -> None:
    task = attach_pcb_model(
        AgentTask(
            task_id="pcb-structured",
            task_type="pcb",
            requirement="Review parsed ESP32 board",
        ),
        _model(floating=True),
    )

    result = PCBAgent().run(task)
    report = PCBReviewReport.model_validate_json(result.output)

    assert result.status is AgentStatus.SUCCESS
    assert report.project_name == "esp32_board"
    assert report.platform == "ESP32"
    assert [issue.id for issue in report.issues] == [
        "pcb-structure-floating-pins"
    ]
    assert report.issues[0].evidence == ["U1.2 has no assigned net."]
    assert report.passed_rules == [
        "pcb-structure-power-net",
        "pcb-structure-ground-net",
    ]
    assert report.metadata["review_mode"] == "deterministic_structured"
    assert report.metadata["source_format"] == "kicad_pcb"
    assert "DRC was not executed" in report.summary


def test_agent_rejects_forged_model_envelope_without_leaking_payload() -> None:
    result = PCBAgent().run(
        AgentTask(
            task_id="pcb-forged",
            task_type="pcb",
            requirement="Review parsed board",
            metadata={
                "_pcb_model_context": {
                    "pcb_model": "C:/Users/private/PRIVATE_PCB_SENTINEL"
                }
            },
        )
    )

    serialized = f"{result.output} {result.metadata}"
    assert result.status is AgentStatus.ERROR
    assert result.output == "PCB requirement analysis failed"
    assert "PRIVATE_PCB_SENTINEL" not in serialized
    assert "C:/Users" not in serialized


def test_agent_public_signatures_and_legacy_path_remain_unchanged() -> None:
    assert str(inspect.signature(PCBAgent.__init__)) == (
        "(self, *, analyzer: 'PCBRequirementAnalyzer | None' = None, "
        "retriever: 'PCBKnowledgeRetriever | None' = None, "
        "rule_engine: 'PCBRuleEngine | None' = None, "
        "reviewer: 'PCBReviewer | None' = None, "
        "validator: 'PCBValidator | None' = None) -> 'None'"
    )
    assert str(inspect.signature(PCBAgent.run)) == (
        "(self, task: 'AgentTask') -> 'AgentResult'"
    )

    result = PCBAgent().run(
        AgentTask(
            task_id="pcb-legacy",
            task_type="pcb",
            requirement="ESP32 SPI PCB review",
        )
    )

    report = PCBReviewReport.model_validate_json(result.output)
    assert result.status is AgentStatus.SUCCESS
    assert report.metadata["review_mode"] == "deterministic_unverified"
    assert report.summary == (
        "Deterministic PCB requirement review used no PCB knowledge documents; "
        "recommendations are generic and unverified."
    )
