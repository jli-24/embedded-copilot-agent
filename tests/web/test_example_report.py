from __future__ import annotations

from embedded_copilot.integration.report import EngineeringReport
from web.example_report import create_esp32_camera_example_report
from web.viewer import build_report_view


def test_esp32_camera_example_is_a_traceable_engineering_report() -> None:
    report = create_esp32_camera_example_report()
    validated = EngineeringReport.model_validate(report.model_dump(mode="python"))
    view = build_report_view(validated)

    assert all(view.sections[name] is not None for name in view.sections)
    assert view.summary["source_agent"] == "SupervisorAgent"
    assert {item["source_agent"] for item in view.evidence} == {
        "PCBAgent",
        "DebugAgent",
    }


def test_esp32_camera_example_excludes_raw_inputs_and_paths() -> None:
    serialized = create_esp32_camera_example_report().model_dump_json()
    forbidden = (
        "#include",
        "app_main(",
        ".pdf",
        ".kicad_pcb",
        "C:/",
        "UnifiedPCBModel",
        "UnifiedDatasheetModel",
    )

    assert all(value not in serialized for value in forbidden)
