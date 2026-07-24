from __future__ import annotations

import pytest

from embedded_copilot.input.models import (
    AttachmentType,
    UnifiedInputContext,
    UserAttachment,
)
from embedded_copilot.integration.context import EngineeringContext
from embedded_copilot.integration.planner import IntegrationPlanner


def _attachment(
    identifier: str,
    filename: str,
    media_type: AttachmentType,
    format_name: str,
) -> UserAttachment:
    return UserAttachment(
        id=identifier,
        filename=filename,
        media_type=media_type,
        content_type="application/octet-stream",
        size_bytes=64,
        metadata={"category": media_type.value, "format": format_name},
    )


def test_planner_selects_agents_from_request_in_dependency_order() -> None:
    selected = IntegrationPlanner().select_agents(
        EngineeringContext(
            request=(
                "Review a datasheet power interface, KiCad PCB layout, "
                "ESP-IDF driver code, and crash log."
            )
        )
    )

    assert selected == (
        "FirmwareAgent",
        "HardwareAgent",
        "PCBAgent",
        "DebugAgent",
    )


def test_planner_uses_attachment_metadata_without_reading_content() -> None:
    context = EngineeringContext(
        request="Review the supplied engineering files.",
        input_context=UnifiedInputContext(
            attachments=(
                _attachment(
                    "source-1",
                    "peripheral_driver.c",
                    AttachmentType.SOURCE_CODE,
                    "c",
                ),
                _attachment(
                    "board-1",
                    "routing.kicad_pcb",
                    AttachmentType.EDA,
                    "kicad_pcb",
                ),
                _attachment(
                    "log-1",
                    "build.log",
                    AttachmentType.LOG,
                    "text",
                ),
            )
        ),
    )

    assert IntegrationPlanner().select_agents(context) == (
        "FirmwareAgent",
        "PCBAgent",
        "DebugAgent",
    )


def test_planner_required_agents_override_is_exact_and_deterministic() -> None:
    planner = IntegrationPlanner()
    context = EngineeringContext(request="firmware pcb debug hardware")

    first = planner.select_agents(
        context,
        required_agents=["pcb", "FIRMWARE", "pcb"],
    )
    second = planner.select_agents(
        context,
        required_agents=["pcb", "FIRMWARE", "pcb"],
    )

    assert first == ("FirmwareAgent", "PCBAgent")
    assert second == first


@pytest.mark.parametrize(
    "required_agents",
    ["firmware", ["unknown"], [""]],
)
def test_planner_rejects_invalid_required_agents(required_agents: object) -> None:
    with pytest.raises(ValueError, match="required_agents"):
        IntegrationPlanner().select_agents(
            EngineeringContext(request="firmware"),
            required_agents=required_agents,
        )


def test_planner_returns_empty_selection_for_unknown_input() -> None:
    assert IntegrationPlanner().select_agents(
        EngineeringContext(request="Improve the product aesthetics.")
    ) == ()


def test_planner_seed_is_supplemented_by_attachment_metadata_not_request() -> None:
    context = EngineeringContext(
        request="Generate firmware code.",
        input_context=UnifiedInputContext(
            attachments=(
                _attachment(
                    "datasheet-1",
                    "mcu-datasheet.pdf",
                    AttachmentType.DOCUMENT,
                    "pdf",
                ),
            )
        ),
    )

    assert IntegrationPlanner().select_agents(
        context,
        seed_agents=["DebugAgent"],
    ) == ("HardwareAgent", "DebugAgent")
