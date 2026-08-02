from __future__ import annotations

import ast
import copy
from pathlib import Path

import pytest
from pydantic import ValidationError

from embedded_copilot.agents.types import AgentStatus
from embedded_copilot.engineering_memory.exceptions import MemoryPermissionDenied
from embedded_copilot.engineering_memory.retrieval import (
    create_engineering_memory_retriever,
)
from embedded_copilot.supervisor.context import (
    SupervisorFallbackTraceEvent,
    SupervisorMemoryTraceEvent,
)

from tests.engineering_memory.test_retrieval_pipeline import (
    _MemoryPort,
    _request,
)
from tests.supervisor.test_failure_fallback import (
    FirmwareAgentFake,
    RecordingGateway,
    RecordingPlanner,
    RecordingRetriever,
    _memory_binding,
    _supervisor,
    _task,
)


ROOT = Path("src/embedded_copilot/supervisor")
FORBIDDEN_IMPORT_FRAGMENTS = (
    "engineering_memory.store",
    "engineering_memory.in_memory",
    "engineering_memory.aggregate",
    "database",
    "filesystem",
)
FORBIDDEN_DATA = (
    "payload",
    "finding_body",
    "approval_body",
    "raw_verification_result",
    "record_id",
    "provider",
    "database",
)


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            values.append(node.module)
    return tuple(values)


def test_v040_supervisor_ast_uses_only_read_side_memory_boundary() -> None:
    imports = tuple(
        name
        for path in ROOT.glob("*.py")
        for name in _imports(path)
    )
    assert not any(
        fragment in imported
        for imported in imports
        for fragment in FORBIDDEN_IMPORT_FRAGMENTS
    )


def test_v040_permission_denial_is_safe_empty_context_without_bypass() -> None:
    port = _MemoryPort(snapshot=object(), failure=MemoryPermissionDenied())
    retriever = create_engineering_memory_retriever(memory_port=port)

    context = retriever.retrieve(_request())

    assert context.records == ()
    assert context.evidence == ()
    assert context.confidence == 0.0
    assert len(port.calls) == 1


def test_v040_dependency_failures_have_allowlisted_content_free_traces() -> None:
    retriever = RecordingRetriever(
        error=RuntimeError("database C:\\private\\memory payload record-7")
    )
    gateway = RecordingGateway()
    agent = FirmwareAgentFake()
    supervisor = _supervisor(
        planner=RecordingPlanner(),
        retriever=retriever,
        gateway=gateway,
        binding=_memory_binding(),
        agent=agent,
    )

    result = supervisor.run(_task())
    serialized = result.model_dump_json().casefold()

    assert result.status is AgentStatus.SUCCESS
    assert retriever.calls == gateway.calls == agent.calls == 1
    assert all(item not in serialized for item in FORBIDDEN_DATA)
    assert all(
        set(event) == {"event", "memory_count"}
        for event in result.metadata["memory_trace"]
    )
    assert all(
        set(event) == {"event", "stage", "memory_count"}
        for event in result.metadata["fallback_trace"]
    )


def test_v040_trace_contracts_are_frozen_strict_and_extra_forbidden() -> None:
    memory = SupervisorMemoryTraceEvent(event="retrieval_succeeded", memory_count=1)
    fallback = SupervisorFallbackTraceEvent(
        event="fallback_used",
        stage="MemoryUnavailable",
        memory_count=0,
    )

    with pytest.raises(ValidationError):
        memory.memory_count = 2  # type: ignore[misc]
    with pytest.raises(ValidationError):
        SupervisorFallbackTraceEvent(
            event="fallback_used",
            stage="MemoryUnavailable",
            memory_count=0,
            payload="secret",  # type: ignore[call-arg]
        )
    assert set(memory.model_dump()) == {"event", "memory_count"}
    assert set(fallback.model_dump()) == {"event", "stage", "memory_count"}


def test_v040_security_fallback_does_not_mutate_caller_inputs() -> None:
    task = _task()
    binding = _memory_binding()
    task_before = copy.deepcopy(task.model_dump(mode="python"))
    binding_before = copy.deepcopy(binding.model_dump(mode="python"))
    supervisor = _supervisor(
        planner=RecordingPlanner(context_result="raise"),
        retriever=RecordingRetriever(),
        gateway=RecordingGateway(),
        binding=binding,
    )

    supervisor.run(task)

    assert task.model_dump(mode="python") == task_before
    assert binding.model_dump(mode="python") == binding_before

