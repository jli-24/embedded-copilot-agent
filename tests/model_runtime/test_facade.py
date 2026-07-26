from __future__ import annotations

import asyncio
import inspect
from typing import get_type_hints

import pytest

import embedded_copilot.model_runtime as public_runtime
from embedded_copilot.conversation.models import ReasoningOutput
from embedded_copilot.conversation.reasoning import ReasoningPort
from embedded_copilot.core.config import Settings
from embedded_copilot.model_runtime import (
    ModelRuntime,
    StatusPort,
    create_model_runtime,
)
from embedded_copilot.model_runtime.health.models import ModelStatusResponse


class _Reasoning:
    async def reason(
        self,
        *,
        user_message_summary: str,
        context_summaries: tuple[str, ...],
        task_intent: str,
    ) -> ReasoningOutput:
        raise AssertionError("not used")


class _Status:
    async def status(self) -> ModelStatusResponse:
        return ModelStatusResponse(
            provider="unavailable",
            status="unavailable",
            capabilities=(),
            model=None,
        )


def test_model_runtime_can_only_be_created_by_production_factory() -> None:
    with pytest.raises(TypeError, match="composition factory"):
        ModelRuntime(_Reasoning(), _Status(), object())  # type: ignore[arg-type]

    runtime = create_model_runtime(Settings(_env_file=None))

    assert isinstance(runtime, ModelRuntime)


def test_facade_exposes_only_protocol_ports_without_runtime_configuration() -> None:
    runtime = create_model_runtime(Settings(_env_file=None))

    assert isinstance(runtime.reasoning_port(), ReasoningPort)
    assert isinstance(runtime.status_port(), StatusPort)
    for forbidden in (
        "gateway",
        "router",
        "registry",
        "provider",
        "providers",
        "health",
        "configuration",
        "settings",
        "config",
        "model_config",
    ):
        assert not hasattr(runtime, forbidden)
        assert not hasattr(runtime.reasoning_port(), forbidden)
        assert not hasattr(runtime.status_port(), forbidden)


def test_facade_methods_are_annotated_with_protocols() -> None:
    reasoning_hints = get_type_hints(ModelRuntime.reasoning_port)
    status_hints = get_type_hints(ModelRuntime.status_port)
    enhancement_hints = get_type_hints(ModelRuntime.enhance_reasoning_port)

    assert reasoning_hints["return"] is ReasoningPort
    assert status_hints["return"] is StatusPort
    assert enhancement_hints["return"].__name__ == "ReasoningPort"
    assert inspect.signature(ModelRuntime.reasoning_port).parameters.keys() == {"self"}
    assert inspect.signature(ModelRuntime.status_port).parameters.keys() == {"self"}
    assert tuple(inspect.signature(ModelRuntime.enhance_reasoning_port).parameters) == (
        "self",
        "base",
    )


def test_status_port_returns_immutable_safe_response_dto() -> None:
    runtime = create_model_runtime(Settings(_env_file=None))

    result = asyncio.run(runtime.status_port().status())

    assert isinstance(result, ModelStatusResponse)
    assert tuple(type(result).model_fields) == (
        "provider",
        "status",
        "capabilities",
        "model",
    )
    assert not hasattr(result, "base_url")
    assert not hasattr(result, "settings")
    assert not hasattr(result, "config")


def test_model_runtime_package_exports_only_facade_factory_and_status_protocol() -> (
    None
):
    assert public_runtime.__all__ == [
        "ModelRuntime",
        "StatusPort",
        "create_model_runtime",
    ]
