from __future__ import annotations

import pytest

from embedded_copilot.agents.types import AgentTask
from embedded_copilot.input.adapters.supervisor import attach_input_context
from embedded_copilot.input.models import (
    AttachmentType,
    UnifiedInputContext,
    UserAttachment,
)
from embedded_copilot.supervisor.analyzer import SupervisorRequirementAnalyzer
from embedded_copilot.supervisor.exceptions import SupervisorAnalysisError
from embedded_copilot.supervisor.planner import SupervisorPlanner


def _context() -> UnifiedInputContext:
    return UnifiedInputContext(
        text="PCB metadata only",
        attachments=(
            UserAttachment(
                id="board-1",
                filename="board.kicad_pcb",
                media_type=AttachmentType.EDA,
                content_type="application/x-kicad-pcb",
                size_bytes=128,
                metadata={"format": "kicad_pcb", "category": "eda"},
            ),
        ),
    )


def _task() -> AgentTask:
    return AgentTask(
        task_id="input-1",
        task_type="routing",
        requirement="Review this ESP32 PCB layout",
        metadata={"project_name": "board-review", "public": "keep"},
    )


def test_analyzer_consumes_only_adapter_envelope_into_typed_context() -> None:
    adapted = attach_input_context(_task(), _context())

    analyzed = SupervisorRequirementAnalyzer().analyze(
        adapted.requirement,
        metadata=adapted.metadata,
    )

    assert analyzed.input_context == _context()
    assert analyzed.metadata == {"public": "keep"}
    assert analyzed.required_agents == ["PCBAgent"]
    serialized = analyzed.model_dump_json()
    assert "board.kicad_pcb" in serialized
    assert "PRIVATE" not in serialized


def test_analyzer_rejects_forged_context_payload_without_leaking_it() -> None:
    adapted = attach_input_context(_task(), _context())
    reserved_key = set(adapted.metadata).difference(_task().metadata).pop()
    forged = {
        **_task().metadata,
        reserved_key: {
            "text": "PRIVATE_SENTINEL",
            "attachments": [],
            "metadata": {},
        },
    }

    with pytest.raises(
        SupervisorAnalysisError,
        match="supervisor requirement analysis failed",
    ) as captured:
        SupervisorRequirementAnalyzer().analyze(
            _task().requirement,
            metadata=forged,
        )

    assert "PRIVATE_SENTINEL" not in str(captured.value)


def test_planner_does_not_propagate_input_context_to_domain_invocations() -> None:
    adapted = attach_input_context(_task(), _context())
    analyzed = SupervisorRequirementAnalyzer().analyze(
        adapted.requirement,
        metadata=adapted.metadata,
    )

    plan = SupervisorPlanner().plan(analyzed)

    serialized = plan.model_dump_json()
    assert "board.kicad_pcb" not in serialized
    assert "input_context" not in serialized
    assert plan.tasks[0].metadata["public"] == "keep"


def test_legacy_analyzer_path_has_no_input_context_requirement() -> None:
    task = _task()

    analyzed = SupervisorRequirementAnalyzer().analyze(
        task.requirement,
        metadata=task.metadata,
    )

    assert analyzed.input_context is None
    assert analyzed.metadata == {"public": "keep"}
