from __future__ import annotations

import pytest

from embedded_copilot.agents.types import AgentTask
from embedded_copilot.input.adapters.supervisor import attach_input_context
from embedded_copilot.input.exceptions import InputValidationError
from embedded_copilot.input.models import (
    AttachmentType,
    UnifiedInputContext,
    UserAttachment,
)


def _context() -> UnifiedInputContext:
    return UnifiedInputContext(
        text="Review the attached PCB metadata",
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
        metadata={"source": "user_upload"},
    )


def _task() -> AgentTask:
    return AgentTask(
        task_id="input-1",
        task_type="routing",
        requirement="Review this ESP32 PCB layout",
        metadata={"nested": {"keep": True}},
    )


def test_adapter_returns_isolated_agent_task_without_schema_change() -> None:
    task = _task()
    context = _context()
    before = task.model_dump(mode="python")

    adapted = attach_input_context(task, context)

    assert adapted is not task
    assert task.model_dump(mode="python") == before
    assert set(AgentTask.model_json_schema()["properties"]) == {
        "task_id",
        "task_type",
        "requirement",
        "metadata",
    }
    assert adapted.metadata["nested"] == {"keep": True}
    reserved = set(adapted.metadata).difference(task.metadata)
    assert len(reserved) == 1
    envelope = adapted.metadata[reserved.pop()]
    assert context.model_dump(mode="json") == envelope.context.model_dump(  # type: ignore[attr-defined]
        mode="json"
    )
    assert envelope.context is not context  # type: ignore[attr-defined]


def test_adapter_rejects_invalid_or_repeated_injection() -> None:
    task = _task()
    context = _context()

    with pytest.raises(InputValidationError, match="input adapter is invalid"):
        attach_input_context("not a task", context)  # type: ignore[arg-type]
    with pytest.raises(InputValidationError, match="input adapter is invalid"):
        attach_input_context(task, "not a context")  # type: ignore[arg-type]
    with pytest.raises(InputValidationError, match="input context already exists"):
        attach_input_context(attach_input_context(task, context), context)
