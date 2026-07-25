from __future__ import annotations

import inspect

from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.engineering.adapter import EngineeringSupervisorAdapter
from embedded_copilot.engineering.models import RealEngineeringEnvelope
from embedded_copilot.input.adapters.supervisor import attach_input_context
from embedded_copilot.input.models import (
    AttachmentType,
    UnifiedInputContext,
    UserAttachment,
)


class _InputAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def adapt(self, context: UnifiedInputContext) -> RealEngineeringEnvelope:
        self.calls += 1
        return RealEngineeringEnvelope()


class _Supervisor:
    def __init__(self) -> None:
        self.tasks: list[AgentTask] = []
        self.result = AgentResult(
            agent_name="SupervisorAgent",
            status=AgentStatus.SUCCESS,
            output="delegated",
        )

    def run(self, task: AgentTask) -> AgentResult:
        self.tasks.append(task)
        return self.result


def test_supervisor_adapter_only_injects_envelope_and_delegates_once() -> None:
    original = attach_input_context(
        AgentTask(
            task_id="engineering-1",
            task_type="end_to_end",
            requirement="Analyze attachments",
            metadata={"public": "keep"},
        ),
        UnifiedInputContext(
            text="metadata only",
            attachments=(
                UserAttachment(
                    id="source-1",
                    filename="main.c",
                    media_type=AttachmentType.SOURCE_CODE,
                    content_type="text/x-c",
                    size_bytes=128,
                    metadata={"category": "source_code", "format": "c"},
                ),
            ),
        ),
    )
    before = original.model_dump_json()
    delegate = _Supervisor()
    input_adapter = _InputAdapter()

    result = EngineeringSupervisorAdapter(
        delegate=delegate,
        input_adapter=input_adapter,
    ).run(original)

    assert result is delegate.result
    assert input_adapter.calls == 1
    assert len(delegate.tasks) == 1
    delegated = delegate.tasks[0]
    assert delegated.task_id == original.task_id
    assert delegated.task_type == original.task_type
    assert delegated.requirement == original.requirement
    assert delegated.metadata["public"] == "keep"
    assert "_real_engineering_input" in delegated.metadata
    assert isinstance(
        delegated.metadata["_real_engineering_input"],
        RealEngineeringEnvelope,
    )
    assert original.model_dump_json() == before


def test_supervisor_adapter_ignores_unsupported_attachments() -> None:
    original = attach_input_context(
        AgentTask(
            task_id="unsupported-1",
            task_type="review",
            requirement="Analyze attachment",
        ),
        UnifiedInputContext(
            attachments=(
                UserAttachment(
                    id="source-unsupported",
                    filename="tool.py",
                    media_type=AttachmentType.SOURCE_CODE,
                    content_type="text/x-python",
                    size_bytes=16,
                    metadata={"category": "source_code", "format": "py"},
                ),
            ),
        ),
    )
    delegate = _Supervisor()
    input_adapter = _InputAdapter()

    result = EngineeringSupervisorAdapter(
        delegate=delegate,
        input_adapter=input_adapter,
    ).run(original)

    assert result is delegate.result
    assert input_adapter.calls == 0
    assert len(delegate.tasks) == 1
    assert "_real_engineering_input" not in delegate.tasks[0].metadata


def test_supervisor_adapter_has_no_workflow_ownership_imports() -> None:
    source = inspect.getsource(
        __import__(
            "embedded_copilot.engineering.adapter",
            fromlist=["EngineeringSupervisorAdapter"],
        )
    ).casefold()

    for forbidden in (
        "supervisor.analyzer",
        "supervisor.planner",
        "supervisor.dispatcher",
        "supervisor.aggregator",
        "integration.executor",
        "integration.aggregator",
    ):
        assert forbidden not in source
