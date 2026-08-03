from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from embedded_copilot.api.models import AnalyzeResponse
from embedded_copilot.services.execution import ExecutionSnapshot, ExecutionStatus
from web.example_report import create_esp32_camera_example_report
from web.navigation import PAGES


def test_navigation_exposes_four_product_views_in_stable_order() -> None:
    assert PAGES == ("概览", "工程工作台", "评测基准", "示例报告")


def test_streamlit_app_loads_with_overview_as_default_page() -> None:
    app = AppTest.from_file("web/app.py").run(timeout=15)

    assert not app.exception
    assert app.sidebar.radio[0].options == list(PAGES)
    assert app.sidebar.radio[0].value == "概览"
    assert app.title[0].value == "Embedded Copilot"


@pytest.mark.parametrize(
    ("page", "title"),
    (
        ("概览", "Embedded Copilot"),
        ("工程工作台", "工程工作台"),
        ("评测基准", "评测基准"),
        ("示例报告", "ESP32 Camera 示例报告"),
    ),
)
def test_each_product_view_loads_without_runtime_exceptions(
    page: str,
    title: str,
) -> None:
    app = AppTest.from_file("web/app.py").run(timeout=15)

    app.sidebar.radio[0].set_value(page).run(timeout=15)

    assert not app.exception
    assert app.title[0].value == title


def test_benchmark_localizes_unavailable_agent_latency() -> None:
    app = AppTest.from_file("web/app.py").run(timeout=15)

    app.sidebar.radio[0].set_value("评测基准").run(timeout=15)

    captions = [item.value for item in app.caption]
    assert "Agent 延迟：不可用" in captions
    assert all("unavailable" not in value for value in captions)


def test_analyze_clears_stale_execution_state_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingProductApiClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def analyze(self, *args: object, **kwargs: object) -> object:
            from web.client import ProductApiError

            raise ProductApiError("无法连接 Product API，请确认服务是否可用。")

        def close(self) -> None:
            pass

    monkeypatch.setattr("web.client.ProductApiClient", FailingProductApiClient)
    app = AppTest.from_file("web/app.py").run(timeout=15)
    app.sidebar.radio[0].set_value("工程工作台").run(timeout=15)
    app.session_state["execution_id"] = "stale-execution"
    app.session_state["report"] = "stale-report"
    app.text_area[0].set_value("Analyze a sensor interface")

    next(button for button in app.button if button.label == "Analyze").click().run(
        timeout=15
    )

    assert not app.exception
    assert "execution_id" not in app.session_state
    assert "report" not in app.session_state
    assert app.error[0].value == "无法连接 Product API，请确认服务是否可用。"


def test_completed_execution_fetches_report_once_across_reruns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"analyze": 0, "status": 0, "report": 0}

    class CompletedProductApiClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def analyze(self, *args: object, **kwargs: object) -> AnalyzeResponse:
            calls["analyze"] += 1
            return AnalyzeResponse(execution_id="exec-1", status=ExecutionStatus.QUEUED)

        def status(self, execution_id: str) -> ExecutionSnapshot:
            calls["status"] += 1
            return ExecutionSnapshot(
                execution_id=execution_id,
                status=ExecutionStatus.COMPLETED,
            )

        def report(self, execution_id: str):
            calls["report"] += 1
            return create_esp32_camera_example_report()

        def close(self) -> None:
            pass

    monkeypatch.setattr("web.client.ProductApiClient", CompletedProductApiClient)
    app = AppTest.from_file("web/app.py").run(timeout=15)
    app.sidebar.radio[0].set_value("工程工作台").run(timeout=15)
    app.text_area[0].set_value("分析传感器接口")

    next(button for button in app.button if button.label == "Analyze").click().run(
        timeout=15
    )

    assert not app.exception
    assert calls == {"analyze": 1, "status": 1, "report": 1}
    assert app.info[0].value == "任务状态：Completed"
    assert "report" in app.session_state
    assert app.subheader[0].value == "EngineeringReport"

    app.run(timeout=15)

    assert not app.exception
    assert calls == {"analyze": 1, "status": 1, "report": 1}


def test_failed_execution_clears_report_and_hides_server_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailedProductApiClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def status(self, execution_id: str) -> ExecutionSnapshot:
            return ExecutionSnapshot(
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                error="request=/internal/private token=SECRET_TOKEN",
            )

        def close(self) -> None:
            pass

    monkeypatch.setattr("web.client.ProductApiClient", FailedProductApiClient)
    app = AppTest.from_file("web/app.py").run(timeout=15)
    app.sidebar.radio[0].set_value("工程工作台").run(timeout=15)
    app.session_state["execution_id"] = "exec-failed"
    app.session_state["report"] = create_esp32_camera_example_report()

    app.run(timeout=15)

    assert not app.exception
    assert "report" not in app.session_state
    assert app.error[0].value == "分析任务失败，请稍后重试。"
    assert "SECRET_TOKEN" not in app.error[0].value
