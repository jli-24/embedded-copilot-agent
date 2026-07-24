from __future__ import annotations

import copy
from collections.abc import Mapping

from pydantic import field_validator

from embedded_copilot.agents.types import AgentTask
from embedded_copilot.input.exceptions import InputValidationError
from embedded_copilot.input.models import UnifiedInputContext
from embedded_copilot.schemas.result import ContractModel


_CONTEXT_KEY = "_supervisor_input_context"


class _SupervisorInputEnvelope(ContractModel):
    context: UnifiedInputContext

    @field_validator("context", mode="before")
    @classmethod
    def isolate_context(cls, value: object) -> object:
        return copy.deepcopy(value)


def _copy_context(context: UnifiedInputContext) -> UnifiedInputContext:
    return UnifiedInputContext.model_validate(
        copy.deepcopy(context.model_dump(mode="python"))
    )


def attach_input_context(
    task: AgentTask,
    context: UnifiedInputContext,
) -> AgentTask:
    if not isinstance(task, AgentTask) or not isinstance(
        context,
        UnifiedInputContext,
    ):
        raise InputValidationError("input adapter is invalid")
    try:
        payload = copy.deepcopy(task.model_dump(mode="python"))
        metadata = payload["metadata"]
        if not isinstance(metadata, dict):
            raise TypeError("invalid task metadata")
        if _CONTEXT_KEY in metadata:
            raise InputValidationError("input context already exists")
        metadata[_CONTEXT_KEY] = _SupervisorInputEnvelope(
            context=_copy_context(context)
        )
        return AgentTask.model_validate(payload)
    except InputValidationError:
        raise
    except Exception:
        raise InputValidationError("input adapter is invalid") from None


def _consume_input_context(
    metadata: Mapping[str, object] | None,
) -> tuple[dict[str, object], UnifiedInputContext | None]:
    try:
        copied = copy.deepcopy(dict(metadata or {}))
        raw_context = copied.pop(_CONTEXT_KEY, None)
        if raw_context is None:
            return copied, None
        if not isinstance(raw_context, _SupervisorInputEnvelope):
            raise TypeError("invalid input envelope")
        return copied, _copy_context(raw_context.context)
    except Exception:
        raise InputValidationError("input context is invalid") from None
