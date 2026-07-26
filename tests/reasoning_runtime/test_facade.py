from __future__ import annotations

import inspect

import pytest

import embedded_copilot.reasoning_runtime as public_runtime
from embedded_copilot.reasoning_runtime import (
    ReasoningPort,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningRuntime,
    create_reasoning_runtime,
)


class _Port:
    async def analyze(self, request: ReasoningRequest) -> ReasoningResponse:
        raise AssertionError("not used")


def test_runtime_can_only_be_created_by_factory() -> None:
    with pytest.raises(TypeError, match="composition factory"):
        ReasoningRuntime(_Port())

    runtime = create_reasoning_runtime()

    assert isinstance(runtime, ReasoningRuntime)
    assert isinstance(runtime.reasoning_port(), ReasoningPort)


def test_facade_and_port_expose_only_analysis_boundary() -> None:
    assert {
        name
        for name, value in ReasoningRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"reasoning_port"}
    assert {
        name
        for name, value in ReasoningPort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"analyze"}
    assert tuple(inspect.signature(ReasoningPort.analyze).parameters) == (
        "self",
        "request",
    )


def test_package_has_exact_public_exports() -> None:
    assert public_runtime.__all__ == [
        "CapabilityEntry",
        "NextStep",
        "ReasoningAnalysisTimeout",
        "ReasoningContextConflict",
        "ReasoningContextNotFound",
        "ReasoningContextSnapshot",
        "ReasoningError",
        "ReasoningPort",
        "ReasoningRequest",
        "ReasoningRequestRejected",
        "ReasoningResponse",
        "ReasoningRuntime",
        "ReasoningRuntimeUnavailable",
        "ReasoningSummary",
        "ReasoningTrace",
        "RiskCandidate",
        "RuleResult",
        "SourceType",
        "SupportingReference",
        "create_reasoning_runtime",
    ]
