from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.agent_execution import (
    AgentBindingMetadata,
    AgentExecutionRuntime,
    AgentExecutionInputContext,
    AgentExecutionRequest,
    ExecutionContextReference,
    ExecutionContextSourceType,
    agent_binding_fingerprint,
)

from .conftest import request_for, result_for


def test_request_contract_is_frozen_strict_and_extra_forbidden() -> None:
    request = request_for()

    with pytest.raises(ValidationError):
        request.task_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        AgentExecutionRequest.model_validate(
            {
                **request.model_dump(mode="python"),
                "payload": "raw memory body",
            }
        )
    with pytest.raises(ValidationError):
        AgentExecutionInputContext(
            context_id="context-1",
            summary="Safe summary.",
            references=[
                ExecutionContextReference(
                    source_type=ExecutionContextSourceType.WORKFLOW,
                    reference_id="reference-1",
                )
            ],
        )


def test_request_rejects_naive_time_and_sensitive_context() -> None:
    request = request_for()

    with pytest.raises(ValidationError):
        AgentExecutionRequest(
            **{
                **request.model_dump(mode="python"),
                "timestamp": datetime(2026, 8, 2, 9, 0),
            }
        )
    with pytest.raises(ValidationError):
        AgentExecutionInputContext.model_validate(
            {
                **request.input_context.model_dump(mode="python"),
                "memory_body": "internal record",
            }
        )


def test_result_and_binding_fingerprints_reject_tampering(execution_request) -> None:
    result = result_for(execution_request)

    with pytest.raises(ValidationError):
        type(result).model_validate(
            result.model_copy(update={"summary": "Changed summary."})
        )

    values = {
        "binding_id": "binding-firmware",
        "agent_type": "FIRMWARE",
        "capabilities": ("EXECUTE_TASK",),
    }
    with pytest.raises(ValidationError):
        AgentBindingMetadata(
            **values,
            fingerprint="sha256:" + "0" * 64,
        )
    assert agent_binding_fingerprint(**values).startswith("sha256:")


def test_binding_rejects_duplicate_capabilities() -> None:
    with pytest.raises(ValidationError):
        AgentBindingMetadata(
            binding_id="binding-firmware",
            agent_type="FIRMWARE",
            capabilities=("EXECUTE_TASK", "EXECUTE_TASK"),
            fingerprint="sha256:" + "0" * 64,
        )


def test_runtime_facade_requires_factory_and_exposes_no_internal_accessors() -> None:
    with pytest.raises(TypeError):
        AgentExecutionRuntime(object())  # type: ignore[arg-type]

    public_methods = {
        name for name in dir(AgentExecutionRuntime) if not name.startswith("_")
    }
    assert public_methods == {"execution_port"}
