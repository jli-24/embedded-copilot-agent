from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_intelligence import (
    EngineeringIntelligenceRequest,
    EngineeringRequirementRequest,
    RequirementConstraint,
    create_engineering_intelligence_runtime,
    project_engineering_project,
)

from .conftest import NOW


def test_requirement_agent_extracts_only_explicit_engineering_requirements(
    interface_project,
) -> None:
    port = create_engineering_intelligence_runtime().engineering_intelligence_port()
    request = EngineeringRequirementRequest(
        project=project_engineering_project(interface_project),
        session_id="session-1",
        message_id="message-1",
        requirement_summary="设计一个 ESP32-S3 智能摄像头，使用 OV2640 和 Wi-Fi，低功耗运行。",
        requested_at=NOW,
    )

    document = port.analyze_requirement(request)

    assert document.product == "SMART_CAMERA"
    assert document.functional_requirements == (
        "VIDEO_CAPTURE",
        "WIRELESS_TRANSMISSION",
    )
    assert document.hardware_constraints == (
        RequirementConstraint(key="CAMERA", value="OV2640"),
        RequirementConstraint(key="MCU", value="ESP32-S3"),
    )
    assert document.power_requirements == ("LOW_POWER_OPERATION",)
    assert document.communication_requirements == ("WIFI",)
    assert document.review_required is True
    assert "requirement_summary" not in document.model_dump_json()


def test_requirement_agent_does_not_infer_wifi_from_camera(interface_project) -> None:
    port = create_engineering_intelligence_runtime().engineering_intelligence_port()
    document = port.analyze_requirement(
        EngineeringRequirementRequest(
            project=project_engineering_project(interface_project),
            session_id="session-1",
            message_id="message-1",
            requirement_summary="设计一个 ESP32-S3 智能摄像头。",
            requested_at=NOW,
        )
    )
    assert "VIDEO_CAPTURE" in document.functional_requirements
    assert "WIRELESS_TRANSMISSION" not in document.functional_requirements
    assert document.communication_requirements == ()


def test_planning_agent_builds_deterministic_task_tree(interface_project) -> None:
    port = create_engineering_intelligence_runtime().engineering_intelligence_port()
    request = EngineeringRequirementRequest(
        project=project_engineering_project(interface_project),
        session_id="session-1",
        message_id="message-1",
        requirement_summary="Design an ESP32-S3 camera with Wi-Fi.",
        requested_at=NOW,
    )
    document = port.analyze_requirement(request)

    first = port.create_plan(document)
    second = port.create_plan(document)

    assert first == second
    assert tuple(task.domain.value for task in first.tasks) == (
        "HARDWARE",
        "PCB",
        "FIRMWARE",
        "TESTING",
        "OPTIMIZATION",
    )
    assert first.tasks[1].dependencies == ("01-hardware",)
    assert first.tasks[3].dependencies == ("02-pcb", "03-firmware")
    assert first.tasks[4].dependencies == ("04-testing",)
    assert first.review_required is True


def test_requirement_and_pipeline_inputs_are_strict(interface_project) -> None:
    project = project_engineering_project(interface_project)
    with pytest.raises(ValidationError):
        EngineeringRequirementRequest(
            project=project,
            session_id="session-1",
            message_id="message-1",
            requirement_summary="C:\\workspace\\secret.txt",
            requested_at=NOW,
        )
    with pytest.raises(ValidationError):
        EngineeringIntelligenceRequest(
            project=project,
            session_id="session-1",
            message_id="message-1",
            requirement_summary="Design a camera.",
            evidence=[],  # type: ignore[arg-type]
            requested_at=NOW,
        )
