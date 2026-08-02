from __future__ import annotations

from copy import deepcopy

from embedded_copilot.engineering_intelligence import (
    EngineeringIntelligenceRequest,
    create_engineering_intelligence_runtime,
    project_engineering_project,
)

from .conftest import NOW


def test_complete_pipeline_returns_requirement_plan_context_and_progress(
    interface_project,
) -> None:
    port = create_engineering_intelligence_runtime().engineering_intelligence_port()
    project = project_engineering_project(interface_project)
    request = EngineeringIntelligenceRequest(
        project=project,
        session_id="session-1",
        message_id="message-1",
        requirement_summary="设计一个 ESP32-S3 智能摄像头，使用 Wi-Fi。",
        evidence=(),
        requested_at=NOW,
    )
    before = deepcopy(request.model_dump(mode="json"))

    first = port.prepare_project(request)
    second = port.prepare_project(request)

    assert first == second
    assert first.requirement.product == "SMART_CAMERA"
    assert len(first.plan.tasks) == 5
    assert first.context.project.project_id == "project-1"
    assert tuple(event.sequence for event in first.progress_events) == tuple(
        range(1, 7)
    )
    assert tuple(event.stage.value for event in first.progress_events) == (
        "REQUIREMENT",
        "REQUIREMENT",
        "PLANNING",
        "PLANNING",
        "KNOWLEDGE",
        "KNOWLEDGE",
    )
    assert request.model_dump(mode="json") == before


def test_runtime_facade_is_stateless_and_isolated(interface_project) -> None:
    runtime = create_engineering_intelligence_runtime()
    first_port = runtime.engineering_intelligence_port()
    second_port = runtime.engineering_intelligence_port()
    assert first_port is second_port
    for forbidden in (
        "settings",
        "config",
        "session_store",
        "database",
        "memory_port",
        "knowledge_port",
        "supervisor",
    ):
        assert not hasattr(runtime, forbidden)
