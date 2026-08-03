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


def test_esp32_camera_example_uses_chinese_product_copy() -> None:
    serialized = create_esp32_camera_example_report().model_dump_json()

    assert "ESP32 Camera 工程审查已完成" in serialized
    assert "确认电容布局" in serialized
    assert "检查组件注册" in serialized
    assert "engineering review completed" not in serialized
