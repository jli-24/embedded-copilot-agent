from __future__ import annotations

import ast
import copy
import inspect
import textwrap

from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.input.adapters.supervisor import attach_input_context
from embedded_copilot.input.models import UnifiedInputContext
from embedded_copilot.supervisor.agent import SupervisorAgent
from embedded_copilot.supervisor.dispatcher import AgentDispatcher

from .test_dispatcher import RecordingAgent, _parent_task, _plan, _success
from .test_memory_supervisor_integration import (
    RecordingRetriever,
    _memory_binding,
    _supervisor,
    _task,
)


FORBIDDEN_HANDOFF_KEYS = {
    "approval",
    "approval_body",
    "audit_metadata",
    "context_fingerprint",
    "evidence",
    "finding",
    "memory_context",
    "memory_records",
    "payload",
    "permission",
    "provider",
    "ranking",
    "record_id",
    "retrieval",
    "verification",
    "verification_history",
}


def test_safe_task_preserves_typed_context_without_serialization_roundtrip() -> None:
    task = attach_input_context(
        _task(),
        UnifiedInputContext(text="typed supervisor context"),
    )
    original_context = task.metadata["_supervisor_input_context"]

    safe_task = SupervisorAgent._safe_task(task)
    safe_context = safe_task.metadata["_supervisor_input_context"]

    assert type(safe_context) is type(original_context)
    assert safe_context is not original_context
    assert safe_context.model_dump() == original_context.model_dump()  # type: ignore[union-attr]


def test_safe_task_has_no_serialization_roundtrip() -> None:
    tree = ast.parse(textwrap.dedent(inspect.getsource(SupervisorAgent._safe_task)))
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert {"model_dump", "model_dump_json"}.isdisjoint(called_attributes)


def test_forged_input_envelope_fails_closed_without_leaking_content() -> None:
    task = AgentTask(
        task_id="forged-input-envelope",
        task_type="firmware",
        requirement="review firmware structure",
        metadata={
            "required_agents": ["firmware"],
            "_supervisor_input_context": {
                "context": {"text": "PRIVATE_TYPED_CONTEXT_SENTINEL"}
            },
        },
    )
    supervisor, _, agent = _supervisor()

    result = supervisor.run(task)

    assert result.status is AgentStatus.ERROR
    assert result.output == "supervisor requirement analysis failed"
    assert agent.tasks == []
    assert "PRIVATE_TYPED_CONTEXT_SENTINEL" not in result.model_dump_json()


def test_v040_dispatch_handoff_excludes_memory_internal_contracts() -> None:
    task = _task().model_copy(
        update={
            "metadata": {
                **_task().metadata,
                "memory_records": [{"record_id": "record-1"}],
                "audit_metadata": {"provider": "database"},
                "nested": {"payload": "secret"},
                "execution_parameters": {"mode": "review"},
            }
        }
    )
    task_before = copy.deepcopy(task.model_dump(mode="python"))
    retriever = RecordingRetriever()
    supervisor, planner, agent = _supervisor(
        retriever=retriever,
        binding=_memory_binding(),
    )

    result = supervisor.run(task)

    assert result.status is AgentStatus.SUCCESS
    assert len(planner.contexts) == 1
    assert len(agent.tasks) == 1
    handoff = agent.tasks[0].model_dump(mode="python")
    assert handoff["metadata"]["execution_parameters"] == {"mode": "review"}
    assert not FORBIDDEN_HANDOFF_KEYS.intersection(handoff["metadata"])
    assert "planning_context" not in handoff["metadata"]
    assert task.model_dump(mode="python") == task_before


def test_v040_dispatch_rejects_or_projects_unsafe_legacy_agent_metadata() -> None:
    project = FirmwareProject(name="demo", platform="ESP32")
    unsafe = AgentResult(
        agent_name="FirmwareAgent",
        status=AgentStatus.SUCCESS,
        output=project.model_dump_json(),
        metadata={
            "summary": "validated firmware projection",
            "artifact_reference": "artifact:firmware:1",
            "validation_result": {
                "status": "passed",
                "checks": (
                    {"name": "schema", "record_id": "record-1"},
                    {"name": "content", "payload": "secret"},
                ),
            },
            "memory_records": [{"record_id": "record-1", "payload": "secret"}],
            "audit_metadata": {"provider": "database"},
        },
    )
    dispatcher = AgentDispatcher([RecordingAgent("FirmwareAgent", unsafe)])

    returned = dispatcher.dispatch(_parent_task(), _plan("FirmwareAgent"))[0]
    serialized = returned.model_dump_json().casefold()

    assert returned.status is AgentStatus.ERROR or all(
        key not in serialized for key in FORBIDDEN_HANDOFF_KEYS
    )
    if returned.status is AgentStatus.SUCCESS:
        assert returned.metadata["summary"] == "validated firmware projection"
        assert returned.metadata["artifact_reference"] == "artifact:firmware:1"
        assert returned.metadata["validation_result"] == {
            "status": "passed",
            "checks": (
                {"name": "schema"},
                {"name": "content"},
            ),
        }


def test_v040_dispatch_invalid_exception_and_timeout_are_safe_and_not_retried() -> None:
    for failure in (
        RuntimeError("private payload C:\\workspace\\firmware.c"),
        TimeoutError("private timeout provider"),
    ):
        agent = RecordingAgent(
            "FirmwareAgent",
            object(),
            error=failure,
        )
        returned = AgentDispatcher([agent]).dispatch(
            _parent_task(),
            _plan("FirmwareAgent"),
        )[0]
        serialized = returned.model_dump_json().casefold()
        assert returned.status is AgentStatus.ERROR
        assert returned.output == "supervisor dispatch failed"
        assert len(agent.tasks) == 1
        assert "private" not in serialized
        assert "workspace" not in serialized
        assert "provider" not in serialized


def test_v040_dispatch_partial_results_preserve_only_validated_success() -> None:
    firmware = RecordingAgent(
        "FirmwareAgent",
        _success(
            "FirmwareAgent",
            FirmwareProject(name="demo", platform="ESP32").model_dump_json(),
        ),
    )
    hardware = RecordingAgent(
        "HardwareAgent",
        _success("HardwareAgent", "invalid hardware result"),
    )
    returned = AgentDispatcher([firmware, hardware]).dispatch(
        _parent_task(),
        _plan("FirmwareAgent", "HardwareAgent"),
    )

    assert tuple(item.status for item in returned) == (
        AgentStatus.SUCCESS,
        AgentStatus.ERROR,
    )
    assert len(firmware.tasks) == len(hardware.tasks) == 1
    assert "firmware_project" in hardware.tasks[0].metadata


def test_v040_dispatch_agent_mutation_cannot_change_parent_or_plan() -> None:
    parent = _parent_task()
    plan = _plan(
        "FirmwareAgent",
        metadata={"nested": {"values": ["original"]}},
    )
    before = (
        copy.deepcopy(parent.model_dump(mode="python")),
        copy.deepcopy(plan.model_dump(mode="python")),
    )
    agent = RecordingAgent(
        "FirmwareAgent",
        _success(
            "FirmwareAgent",
            FirmwareProject(name="demo", platform="ESP32").model_dump_json(),
        ),
        mutate_input=True,
    )

    AgentDispatcher([agent]).dispatch(parent, plan)

    assert parent.model_dump(mode="python") == before[0]
    assert plan.model_dump(mode="python") == before[1]
    assert len(agent.tasks) == 1


def test_v040_dispatch_result_contract_rejects_wrong_domain_type() -> None:
    wrong = RecordingAgent(
        "FirmwareAgent",
        _success(
            "FirmwareAgent",
            HardwarePlan(
                project_name="demo",
                platform="ESP32",
                mcu="ESP32-S3",
                rationale="typed mismatch",
            ).model_dump_json(),
        ),
    )

    returned = AgentDispatcher([wrong]).dispatch(
        _parent_task(),
        _plan("FirmwareAgent"),
    )[0]

    assert returned.status is AgentStatus.ERROR
    assert returned.output == "supervisor handoff validation failed"
