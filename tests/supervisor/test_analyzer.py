import pytest

from embedded_copilot.supervisor.analyzer import SupervisorRequirementAnalyzer
from embedded_copilot.supervisor.exceptions import SupervisorAnalysisError


def test_analyzer_recognizes_agents_in_first_occurrence_order() -> None:
    analysis = SupervisorRequirementAnalyzer().analyze(
        "Review PCB layout, then firmware code and hardware components"
    )

    assert analysis.required_agents == [
        "PCBAgent",
        "FirmwareAgent",
        "HardwareAgent",
    ]


def test_analyzer_recognizes_chinese_whole_system_design() -> None:
    analysis = SupervisorRequirementAnalyzer().analyze(
        "设计一个基于 ESP32-S3 的摄像头终端方案"
    )

    assert analysis.required_agents == [
        "FirmwareAgent",
        "HardwareAgent",
        "PCBAgent",
    ]


def test_analyzer_does_not_select_all_for_generic_design_word() -> None:
    analysis = SupervisorRequirementAnalyzer().analyze("请改进产品设计")

    assert analysis.required_agents == []


def test_analyzer_metadata_overrides_control_fields_without_leaking_them() -> None:
    source_metadata = {
        "project_name": "  controlled_project ",
        "required_agents": ["pcb", "FIRMWARE", "pcb"],
        "constraints": [" offline ", "OFFLINE", " deterministic "],
        "nested": {"values": ["keep"]},
    }

    analysis = SupervisorRequirementAnalyzer().analyze(
        "hardware component selection",
        metadata=source_metadata,
    )
    source_metadata["nested"]["values"].append("mutated")  # type: ignore[index,union-attr]

    assert analysis.project_name == "controlled_project"
    assert analysis.required_agents == ["PCBAgent", "FirmwareAgent"]
    assert analysis.constraints == ["offline", "deterministic"]
    assert analysis.metadata == {"nested": {"values": ["keep"]}}


def test_analyzer_drops_supervisor_owned_handoff_metadata() -> None:
    analysis = SupervisorRequirementAnalyzer().analyze(
        "hardware component and PCB layout",
        metadata={
            "firmware_project": {"forged": True},
            "hardware_plan": {"stale": True},
            "trace": "keep",
        },
    )

    assert analysis.metadata == {"trace": "keep"}


@pytest.mark.parametrize(
    "metadata",
    [
        {"required_agents": ["unknown"]},
        {"required_agents": "firmware"},
        {"project_name": " "},
        {"constraints": [""]},
    ],
)
def test_analyzer_rejects_invalid_metadata_overrides(metadata: object) -> None:
    with pytest.raises(SupervisorAnalysisError):
        SupervisorRequirementAnalyzer().analyze("firmware", metadata=metadata)
