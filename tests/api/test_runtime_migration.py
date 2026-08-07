from __future__ import annotations

import asyncio

from embedded_copilot.api import main as api_main
from embedded_copilot.api.main import create_app
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.services.config import Settings


class _ChatService:
    async def chat(self, message: str, *, trace_id: str) -> ChatResponse:
        return ChatResponse(answer=message, trace_id=trace_id)


class _LegacyRuntime:
    def __init__(self) -> None:
        self.started = False
        self.closed = False

    async def start(self) -> None:
        self.started = True

    async def close(self) -> None:
        self.closed = True


def test_default_analysis_service_uses_explicit_legacy_runtime(
    monkeypatch,
) -> None:
    legacy = _LegacyRuntime()
    calls: list[Settings] = []

    def fake_build_legacy_runtime(settings: Settings) -> _LegacyRuntime:
        calls.append(settings)
        return legacy

    monkeypatch.setattr(api_main, "build_legacy_runtime", fake_build_legacy_runtime)
    app = create_app(settings=Settings(_env_file=None), service=_ChatService())

    async def exercise() -> None:
        async with app.router.lifespan_context(app):
            assert app.state.copilot_service.__class__ is _ChatService
            assert app.state.analysis_service is legacy
            assert legacy.started is True

    asyncio.run(exercise())

    assert len(calls) == 1
    assert legacy.closed is True
