from __future__ import annotations

import pytest

from embedded_copilot.context_runtime import (
    EngineeringContextPort,
    EngineeringContextRuntime,
)
from embedded_copilot.context_runtime.contracts import (
    EngineeringContextRequest,
    EngineeringContextResponse,
    EngineeringContextSummary,
)


class _Port:
    async def compose(
        self,
        request: EngineeringContextRequest,
    ) -> EngineeringContextResponse:
        return EngineeringContextResponse(
            context_summary=EngineeringContextSummary(
                context_id="context:0123456789abcdef01234567",
                task_intent=request.task_intent,
            )
        )


def test_facade_exposes_only_context_port() -> None:
    port = _Port()
    runtime = EngineeringContextRuntime._compose(port)

    assert runtime.context_port() is port
    assert isinstance(runtime.context_port(), EngineeringContextPort)
    assert {
        name
        for name, value in EngineeringContextRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"context_port"}
    for forbidden in (
        "composer",
        "resolver",
        "settings",
        "configuration",
        "workspace",
        "repository",
    ):
        with pytest.raises(AttributeError):
            getattr(runtime, forbidden)
