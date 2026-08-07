from __future__ import annotations

import asyncio

from embedded_copilot.api import main as api_main
from embedded_copilot.api.main import create_app
from embedded_copilot.services.canonical_runtime import build_canonical_runtime
from embedded_copilot.services.legacy_runtime import build_legacy_runtime
from embedded_copilot.services.runtime import build_analysis_service, build_runtime


class _Service:
    async def start(self) -> None:
        pass

    async def close(self) -> None:
        pass


def test_legacy_imports_are_compatibility_aliases() -> None:
    assert build_runtime is build_canonical_runtime
    assert build_analysis_service is build_legacy_runtime
    assert build_runtime.__module__ == (
        "embedded_copilot.services.canonical_runtime"
    )
    assert build_analysis_service.__module__ == (
        "embedded_copilot.services.legacy_runtime"
    )


def test_explicit_services_disable_both_default_runtime_compositions(monkeypatch) -> None:
    def fail_canonical(*args, **kwargs):
        raise AssertionError("canonical runtime fallback was invoked")

    def fail_legacy(*args, **kwargs):
        raise AssertionError("legacy runtime fallback was invoked")

    monkeypatch.setattr(api_main, "build_canonical_runtime", fail_canonical)
    monkeypatch.setattr(api_main, "build_legacy_runtime", fail_legacy)

    app = create_app(service=_Service(), analysis_service=_Service())

    async def exercise() -> None:
        async with app.router.lifespan_context(app):
            assert isinstance(app.state.copilot_service, _Service)
            assert isinstance(app.state.analysis_service, _Service)

    asyncio.run(exercise())
