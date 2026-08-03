from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import streamlit as st

from embedded_copilot.api.models import AnalysisAgent
from embedded_copilot.input.models import UserAttachment
from embedded_copilot.integration.report import render_report_markdown
from embedded_copilot.services.execution import ExecutionStatus
from web.attachments import build_attachment_metadata
from web.benchmark import build_benchmark_view, release_benchmark_report
from web.client import ProductApiClient, ProductApiError
from web.demo import DemoManifest, load_demo_manifest
from web.example_report import create_esp32_camera_example_report
from web.navigation import PAGES
from web.viewer import ReportView, build_report_view


API_URL = os.getenv("EMBEDDED_COPILOT_API_URL", "http://127.0.0.1:8765")
DEMO_MANIFEST = Path(__file__).resolve().parents[1] / "demo" / "esp32_camera" / "manifest.json"
AGENTS: tuple[AnalysisAgent, ...] = ("hardware", "firmware", "pcb", "debug")
AGENT_LABELS: dict[AnalysisAgent, str] = {
    "hardware": "HardwareAgent",
    "firmware": "FirmwareAgent",
    "pcb": "PCBAgent",
    "debug": "DebugAgent",
}
STATUS_LABELS = {
    ExecutionStatus.QUEUED: "Queued",
    ExecutionStatus.RUNNING: "Running",
    ExecutionStatus.COMPLETED: "Completed",
    ExecutionStatus.FAILED: "失败",
}


def _client() -> ProductApiClient:
    return ProductApiClient(API_URL, timeout_seconds=15.0)


def _clear_report() -> None:
    st.session_state.pop("report", None)
    st.session_state.pop("report_execution_id", None)


def _load_demo() -> None:
    manifest = load_demo_manifest(DEMO_MANIFEST)
    st.session_state["demo"] = manifest
    st.session_state["requirement"] = manifest.request
    st.session_state["agents"] = list(manifest.required_agents)
    st.session_state.pop("execution_id", None)
    _clear_report()


def _metadata_rows(attachments: tuple[UserAttachment, ...]) -> list[dict[str, object]]:
    return [
        {
            "文件名": item.filename,
            "类型": item.media_type.value,
            "MIME": item.content_type,
            "大小（字节）": item.size_bytes,
        }
        for item in attachments
    ]


def _render_overview() -> None:
    st.title("Embedded Copilot")
    st.caption("面向嵌入式研发的可追踪工程分析系统")
    st.subheader("工程工作流")
    columns = st.columns(5)
    for column, label in zip(
        columns,
        ("工程需求", "RAG 检索", "任务规划", "Agent 调度", "EngineeringReport"),
        strict=True,
    ):
        with column:
            st.markdown(f"**{label}**")
    st.subheader("技术栈")
    st.write(
        "Python 3.11 · LangGraph · RAG · FastAPI · Pydantic · Streamlit · pytest"
    )


def _render_report(view: ReportView, *, include_trace: bool) -> None:
    st.write(view.summary["text"])
    names = ["HardwareAgent", "FirmwareAgent", "PCBAgent", "DebugAgent", "证据"]
    if include_trace:
        names.extend(("建议", "追踪"))
    tabs = st.tabs(names)
    for tab, name in zip(tabs[:4], ("hardware", "firmware", "pcb", "debug"), strict=True):
        with tab:
            section = view.sections[name]
            if section is None:
                st.caption("暂无经过验证的 Agent 结果。")
            else:
                st.json(section)
    with tabs[4]:
        st.dataframe(view.evidence, hide_index=True)
    if include_trace:
        with tabs[5]:
            st.dataframe(view.recommendations, hide_index=True)
        with tabs[6]:
            st.dataframe(view.trace, hide_index=True)


def _render_workbench() -> None:
    st.title("工程工作台")
    toolbar_left, toolbar_right = st.columns([1, 5])
    with toolbar_left:
        if st.button("Load Demo"):
            _load_demo()
            st.rerun()
    with toolbar_right:
        st.caption("附件仅作为 metadata 处理，Web 不读取附件正文。")

    requirement = st.text_area(
        "工程需求",
        key="requirement",
        height=150,
        placeholder="请描述需要分析的嵌入式工程任务。",
    )
    uploads = st.file_uploader(
        "附件",
        type=["pdf", "kicad_pcb", "kicad_sch", "c", "cpp", "h", "hpp", "log", "txt"],
        accept_multiple_files=True,
    )
    selected_agents = st.multiselect(
        "Agent",
        options=list(AGENTS),
        format_func=lambda agent: AGENT_LABELS[agent],
        key="agents",
    )

    try:
        uploaded_attachments = tuple(
            build_attachment_metadata(upload, f"upload-{index}")
            for index, upload in enumerate(uploads, start=1)
        )
    except (TypeError, ValueError) as exc:
        st.error(str(exc))
        uploaded_attachments = ()

    demo = st.session_state.get("demo")
    demo_manifest = demo if isinstance(demo, DemoManifest) else None
    attachments = (
        uploaded_attachments
        if uploaded_attachments
        else (demo_manifest.attachments if demo_manifest is not None else ())
    )
    if attachments:
        st.dataframe(_metadata_rows(attachments), hide_index=True)

    if st.button("Analyze", type="primary", disabled=not requirement.strip()):
        st.session_state.pop("execution_id", None)
        _clear_report()
        client = _client()
        try:
            response = client.analyze(
                requirement,
                attachments,
                cast(list[AnalysisAgent], selected_agents),
            )
            st.session_state["execution_id"] = response.execution_id
        except ProductApiError as exc:
            st.error(str(exc))
        finally:
            client.close()

    execution_id = st.session_state.get("execution_id")
    report_is_cached = (
        isinstance(execution_id, str)
        and st.session_state.get("report_execution_id") == execution_id
        and "report" in st.session_state
    )
    if isinstance(execution_id, str) and not report_is_cached:
        status_column, refresh_column = st.columns([5, 1])
        client = _client()
        try:
            snapshot = client.status(execution_id)
            with status_column:
                st.info(f"任务状态：{STATUS_LABELS[snapshot.status]}")
            with refresh_column:
                if st.button("刷新"):
                    st.rerun()
            if snapshot.status is ExecutionStatus.COMPLETED:
                st.session_state["report"] = client.report(execution_id)
                st.session_state["report_execution_id"] = execution_id
            elif snapshot.status is ExecutionStatus.FAILED:
                _clear_report()
                st.error("分析任务失败，请稍后重试。")
        except ProductApiError as exc:
            _clear_report()
            st.error(str(exc))
        finally:
            client.close()
    elif isinstance(execution_id, str):
        st.info("任务状态：Completed")

    report_is_cached = (
        isinstance(execution_id, str)
        and st.session_state.get("report_execution_id") == execution_id
        and "report" in st.session_state
    )
    report = st.session_state.get("report") if report_is_cached else None
    if report is not None and isinstance(execution_id, str):
        st.subheader("EngineeringReport")
        _render_report(build_report_view(report), include_trace=True)
        st.download_button(
            "下载 Markdown",
            data=render_report_markdown(report),
            file_name=f"embedded-copilot-{execution_id}.md",
            mime="text/markdown",
        )


def _render_benchmark() -> None:
    st.title("评测基准")
    st.caption("v0.20.1 确定性发布评测快照")
    view = build_benchmark_view(release_benchmark_report())
    columns = st.columns(4)
    columns[0].metric("用例数", view.cases)
    columns[1].metric("成功率", f"{view.success_rate:.0%}")
    columns[2].metric("总延迟", f"{view.latency_ms:.3f} ms")
    columns[3].metric("覆盖率", f"{view.coverage:.0%}")
    agent_latency = (
        "不可用" if view.agent_latency_status == "unavailable" else "未知"
    )
    st.caption(f"Agent 延迟：{agent_latency}")


def _render_example_report() -> None:
    st.title("ESP32 Camera 示例报告")
    st.caption("经过安全裁剪的 EngineeringReport 投影视图")
    _render_report(
        build_report_view(create_esp32_camera_example_report()),
        include_trace=False,
    )


st.set_page_config(page_title="Embedded Copilot", layout="wide")
page = st.sidebar.radio("页面", PAGES, index=0)
if page == "概览":
    _render_overview()
elif page == "工程工作台":
    _render_workbench()
elif page == "评测基准":
    _render_benchmark()
else:
    _render_example_report()
