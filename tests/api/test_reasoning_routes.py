from __future__ import annotations

import asyncio

import httpx
import pytest

from embedded_copilot.api.main import create_app
from embedded_copilot.context_runtime.contracts import (
    EngineeringContextRequest,
    EngineeringContextResponse,
    EngineeringContextSummary,
)
from embedded_copilot.context_runtime.exceptions import (
    EngineeringContextConflict,
    EngineeringContextReferenceNotFound,
    EngineeringContextRejected,
    EngineeringContextTimeout,
    EngineeringContextUnavailable,
)
from embedded_copilot.core.config import Settings
from embedded_copilot.reasoning_runtime import create_reasoning_runtime
from embedded_copilot.schemas.api import ChatResponse

CONTEXT_ID = "context:0123456789abcdef01234567"


class _ChatService:
    async def chat(self, message: str, *, trace_id: str) -> ChatResponse:
        return ChatResponse(
            answer="Existing chat remains available.", trace_id=trace_id
        )


class _ContextPort:
    def __init__(self, outcome: str = "success") -> None:
        self.outcome = outcome
        self.calls: list[EngineeringContextRequest] = []

    async def compose(
        self,
        request: EngineeringContextRequest,
    ) -> EngineeringContextResponse:
        self.calls.append(request)
        error = {
            "not_found": EngineeringContextReferenceNotFound("PRIVATE_REFERENCE"),
            "conflict": EngineeringContextConflict("PRIVATE_CONFLICT"),
            "rejected": EngineeringContextRejected("PRIVATE_REJECTED"),
            "unavailable": EngineeringContextUnavailable("PRIVATE_PROVIDER"),
            "timeout": EngineeringContextTimeout("PRIVATE_TIMEOUT"),
        }.get(self.outcome)
        if error is not None:
            raise error
        return EngineeringContextResponse(
            context_summary=EngineeringContextSummary(
                context_id=CONTEXT_ID,
                task_intent=request.task_intent,
            )
        )


async def _request(
    *,
    context_port: _ContextPort | None,
    reasoning_port: object | None,
    payload: dict[str, object],
) -> httpx.Response:
    app = create_app(
        service=_ChatService(),
        workspace_service=object(),
        experience_service=None,
        context_port=context_port,
        reasoning_port=reasoning_port,
        settings=Settings(_env_file=None),
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/api/v1/copilot/sessions/session:1/reasoning",
                json=payload,
            )


def _payload() -> dict[str, object]:
    return {
        "task_intent": "Review referenced engineering context.",
        "context_id": CONTEXT_ID,
        "reference_ids": [],
    }


def test_reasoning_route_returns_canonical_wire_shape_and_request_trace() -> None:
    context = _ContextPort()
    response = asyncio.run(
        _request(
            context_port=context,
            reasoning_port=create_reasoning_runtime().reasoning_port(),
            payload=_payload(),
        )
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "output_type",
        "reasoning_summary",
        "risks",
        "next_steps",
        "trace",
        "review_required",
    }
    assert body["output_type"] == "reasoning_suggestion"
    assert body["review_required"] is True
    assert body["trace"]["trace_id"] == response.headers["x-trace-id"]
    assert body["trace"]["snapshot_fingerprint"].startswith("sha256:")
    assert context.calls[0].reference_ids == ()


def test_reasoning_route_is_semantically_deterministic_across_request_traces() -> None:
    first = asyncio.run(
        _request(
            context_port=_ContextPort(),
            reasoning_port=create_reasoning_runtime().reasoning_port(),
            payload=_payload(),
        )
    )
    second = asyncio.run(
        _request(
            context_port=_ContextPort(),
            reasoning_port=create_reasoning_runtime().reasoning_port(),
            payload=_payload(),
        )
    )

    first_body = first.json()
    second_body = second.json()
    assert first_body["trace"]["trace_id"] != second_body["trace"]["trace_id"]
    first_body["trace"].pop("trace_id")
    second_body["trace"].pop("trace_id")
    first_body["reasoning_summary"].pop("presentation_summary")
    second_body["reasoning_summary"].pop("presentation_summary")
    assert first_body == second_body


@pytest.mark.parametrize(
    "payload",
    (
        {**_payload(), "path": "private.pdf"},
        {**_payload(), "context_id": "context:bad"},
        {
            "task_intent": "Read C:\\private\\design.pdf",
            "context_id": CONTEXT_ID,
            "reference_ids": [],
        },
    ),
)
def test_reasoning_route_maps_validation_to_safe_422(
    payload: dict[str, object],
) -> None:
    response = asyncio.run(
        _request(
            context_port=_ContextPort(),
            reasoning_port=create_reasoning_runtime().reasoning_port(),
            payload=payload,
        )
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": "reasoning_unavailable",
        "trace_id": response.headers["x-trace-id"],
    }
    assert "private" not in response.text.casefold()


def test_reasoning_route_rejects_context_identity_conflict() -> None:
    response = asyncio.run(
        _request(
            context_port=_ContextPort(),
            reasoning_port=create_reasoning_runtime().reasoning_port(),
            payload={**_payload(), "context_id": "context:ffffffffffffffffffffffff"},
        )
    )

    assert response.status_code == 409
    assert response.json()["error"] == "reasoning_unavailable"


@pytest.mark.parametrize(
    ("outcome", "status_code"),
    (
        ("not_found", 404),
        ("conflict", 409),
        ("rejected", 422),
        ("unavailable", 503),
        ("timeout", 504),
    ),
)
def test_reasoning_route_maps_context_failures_without_private_details(
    outcome: str,
    status_code: int,
) -> None:
    response = asyncio.run(
        _request(
            context_port=_ContextPort(outcome),
            reasoning_port=create_reasoning_runtime().reasoning_port(),
            payload=_payload(),
        )
    )

    assert response.status_code == status_code
    assert response.json() == {
        "error": "reasoning_unavailable",
        "trace_id": response.headers["x-trace-id"],
    }
    assert "PRIVATE_" not in response.text
    assert "traceback" not in response.text.casefold()


def test_reasoning_route_maps_missing_dependency_to_503() -> None:
    response = asyncio.run(
        _request(
            context_port=_ContextPort(),
            reasoning_port=None,
            payload=_payload(),
        )
    )

    assert response.status_code == 503
    assert response.json()["error"] == "reasoning_unavailable"
