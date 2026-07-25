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


API_URL = os.getenv("EMBEDDED_COPILOT_API_URL", "http://127.0.0.1:8000")
DEMO_MANIFEST = Path(__file__).resolve().parents[1] / "demo" / "esp32_camera" / "manifest.json"
AGENTS: tuple[AnalysisAgent, ...] = ("hardware", "firmware", "pcb", "debug")


def _client() -> ProductApiClient:
    return ProductApiClient(API_URL, timeout_seconds=15.0)


def _load_demo() -> None:
    manifest = load_demo_manifest(DEMO_MANIFEST)
    st.session_state["demo"] = manifest
    st.session_state["requirement"] = manifest.request
    st.session_state["agents"] = list(manifest.required_agents)
    st.session_state.pop("execution_id", None)
    st.session_state.pop("report", None)


def _metadata_rows(attachments: tuple[UserAttachment, ...]) -> list[dict[str, object]]:
    return [
        {
            "filename": item.filename,
            "type": item.media_type.value,
            "MIME": item.content_type,
            "size": item.size_bytes,
        }
        for item in attachments
    ]


def _render_overview() -> None:
    st.title("Embedded Copilot")
    st.caption("Traceable engineering analysis for embedded systems")
    st.subheader("Engineering workflow")
    columns = st.columns(5)
    for column, label in zip(
        columns,
        ("Requirement", "Knowledge", "Planning", "Agents", "Report"),
        strict=True,
    ):
        with column:
            st.markdown(f"**{label}**")
    st.subheader("Technology")
    st.write("Python 3.11 · FastAPI · Pydantic · Streamlit · pytest")


def _render_report(view: ReportView, *, include_trace: bool) -> None:
    st.write(view.summary["text"])
    names = ["Hardware", "Firmware", "PCB", "Debug", "Evidence"]
    if include_trace:
        names.extend(("Recommendations", "Trace"))
    tabs = st.tabs(names)
    for tab, name in zip(tabs[:4], ("hardware", "firmware", "pcb", "debug"), strict=True):
        with tab:
            section = view.sections[name]
            if section is None:
                st.caption("No validated Agent result was available.")
            else:
                st.json(section)
    with tabs[4]:
        st.dataframe(view.evidence, use_container_width=True, hide_index=True)
    if include_trace:
        with tabs[5]:
            st.dataframe(view.recommendations, use_container_width=True, hide_index=True)
        with tabs[6]:
            st.dataframe(view.trace, use_container_width=True, hide_index=True)


def _render_workbench() -> None:
    st.title("Workbench")
    toolbar_left, toolbar_right = st.columns([1, 5])
    with toolbar_left:
        if st.button("Load Demo", use_container_width=True):
            _load_demo()
            st.rerun()
    with toolbar_right:
        st.caption("Attachments are handled as metadata only.")

    requirement = st.text_area(
        "Engineering requirement",
        key="requirement",
        height=150,
        placeholder="Describe the embedded engineering task.",
    )
    uploads = st.file_uploader(
        "Attachments",
        type=["pdf", "kicad_pcb", "kicad_sch", "c", "cpp", "h", "hpp", "log", "txt"],
        accept_multiple_files=True,
    )
    selected_agents = st.multiselect("Agents", options=list(AGENTS), key="agents")

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
        st.dataframe(_metadata_rows(attachments), use_container_width=True, hide_index=True)

    if st.button("Analyze", type="primary", disabled=not requirement.strip()):
        client = _client()
        try:
            response = client.analyze(
                requirement,
                attachments,
                cast(list[AnalysisAgent], selected_agents),
            )
            st.session_state["execution_id"] = response.execution_id
            st.session_state.pop("report", None)
        except ProductApiError as exc:
            st.error(str(exc))
        finally:
            client.close()

    execution_id = st.session_state.get("execution_id")
    if isinstance(execution_id, str):
        status_column, refresh_column = st.columns([5, 1])
        client = _client()
        try:
            snapshot = client.status(execution_id)
            with status_column:
                st.info(f"Execution {execution_id}: {snapshot.status.value}")
            with refresh_column:
                if st.button("Refresh", use_container_width=True):
                    st.rerun()
            if snapshot.status is ExecutionStatus.COMPLETED:
                st.session_state["report"] = client.report(execution_id)
            elif snapshot.status is ExecutionStatus.FAILED and snapshot.error:
                st.error(snapshot.error)
        except ProductApiError as exc:
            st.error(str(exc))
        finally:
            client.close()

    report = st.session_state.get("report")
    if report is not None:
        st.subheader("Engineering Report")
        _render_report(build_report_view(report), include_trace=True)
        st.download_button(
            "Download Markdown",
            data=render_report_markdown(report),
            file_name=f"embedded-copilot-{execution_id}.md",
            mime="text/markdown",
        )


def _render_benchmark() -> None:
    st.title("Benchmark")
    st.caption("Deterministic v0.20 release evaluation snapshot")
    view = build_benchmark_view(release_benchmark_report())
    columns = st.columns(4)
    columns[0].metric("Cases", view.cases)
    columns[1].metric("Success Rate", f"{view.success_rate:.0%}")
    columns[2].metric("Total Latency", f"{view.latency_ms:.3f} ms")
    columns[3].metric("Coverage", f"{view.coverage:.0%}")
    st.caption(f"Per-Agent latency: {view.agent_latency_status}")


def _render_example_report() -> None:
    st.title("ESP32 Camera Example")
    st.caption("Sanitized EngineeringReport projection")
    _render_report(
        build_report_view(create_esp32_camera_example_report()),
        include_trace=False,
    )


st.set_page_config(page_title="Embedded Copilot", layout="wide")
page = st.sidebar.radio("View", PAGES, index=0)
if page == "Overview":
    _render_overview()
elif page == "Workbench":
    _render_workbench()
elif page == "Benchmark":
    _render_benchmark()
else:
    _render_example_report()
