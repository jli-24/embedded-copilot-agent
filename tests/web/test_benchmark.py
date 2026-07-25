from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from web.benchmark import build_benchmark_view, release_benchmark_report


def test_benchmark_view_projects_only_safe_release_metrics() -> None:
    report = release_benchmark_report()
    view = build_benchmark_view(report)

    assert view.cases == 3
    assert view.success_rate == 1.0
    assert view.latency_ms == report.metrics.average_latency_ms
    assert view.coverage == 1.0
    assert view.agent_latency_status == "unavailable"
    assert tuple(field.name for field in fields(view)) == (
        "cases",
        "success_rate",
        "latency_ms",
        "coverage",
        "agent_latency_status",
    )
    with pytest.raises(FrozenInstanceError):
        view.cases = 4  # type: ignore[misc]


def test_release_benchmark_snapshot_contains_no_fixture_body_or_paths() -> None:
    serialized = release_benchmark_report().model_dump_json()

    assert "Design an ESP32" not in serialized
    assert ".pdf" not in serialized
    assert ".kicad" not in serialized
    assert "C:/" not in serialized
    assert "AgentResult" not in serialized
