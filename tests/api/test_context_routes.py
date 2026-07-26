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
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.services.config import Settings


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
                context_id="context:0123456789abcdef01234567",
                task_intent=request.task_intent,
            )
        )


async def _request(
    *,
    context_port: _ContextPort | None,
    json: dict[str, object],
) -> httpx.Response:
    app = create_app(
        service=_ChatService(),
        workspace_service=object(),
        experience_service=None,
        context_port=context_port,
        settings=Settings(_env_file=None),
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/api/v1/copilot/sessions/session:1/context",
                json=json,
            )


def test_context_route_returns_nested_safe_summary() -> None:
    port = _ContextPort()
    response = asyncio.run(
        _request(
            context_port=port,
            json={
                "task_intent": "Review referenced embedded context.",
                "reference_ids": ["file:1", "image:1"],
            },
        )
    )

    assert response.status_code == 200
    assert response.json() == {
        "output_type": "context_summary",
        "context_summary": {
            "context_id": "context:0123456789abcdef01234567",
            "task_intent": "Review referenced embedded context.",
            "datasheets": [],
            "files": [],
            "vision": [],
        },
        "review_required": True,
    }
    assert port.calls == [
        EngineeringContextRequest(
            session_id="session:1",
            task_intent="Review referenced embedded context.",
            reference_ids=("file:1", "image:1"),
        )
    ]


@pytest.mark.parametrize(
    "payload",
    (
        {
            "task_intent": "Review referenced embedded context.",
            "reference_ids": [],
            "path": "private.pdf",
        },
        {
            "task_intent": "Read C:\\private\\design.pdf",
            "reference_ids": [],
        },
        {
            "task_intent": "Review referenced embedded context.",
            "reference_ids": ["file:1", "FILE:1"],
        },
    ),
)
def test_context_route_maps_validation_to_safe_422(
    payload: dict[str, object],
) -> None:
    response = asyncio.run(_request(context_port=_ContextPort(), json=payload))

    assert response.status_code == 422
    assert response.json() == {
        "error": "context_unavailable",
        "trace_id": response.headers["x-trace-id"],
    }
    assert "private" not in response.text.casefold()


def test_context_route_maps_missing_dependency_to_safe_503() -> None:
    response = asyncio.run(
        _request(
            context_port=None,
            json={
                "task_intent": "Review referenced embedded context.",
                "reference_ids": [],
            },
        )
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": "context_unavailable",
        "trace_id": response.headers["x-trace-id"],
    }


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
def test_context_route_maps_domain_errors_without_private_details(
    outcome: str,
    status_code: int,
) -> None:
    response = asyncio.run(
        _request(
            context_port=_ContextPort(outcome),
            json={
                "task_intent": "Review referenced embedded context.",
                "reference_ids": ["file:1"],
            },
        )
    )

    assert response.status_code == status_code
    assert response.json() == {
        "error": "context_unavailable",
        "trace_id": response.headers["x-trace-id"],
    }
    assert "PRIVATE_" not in response.text
    assert "traceback" not in response.text.casefold()
