from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error, show_viewer_state
from web.copilot.client import ExperienceApiError
from web.copilot.contracts import integer_value, object_list, text_value
from web.copilot.state import active_session_id


def render() -> None:
    st.title("Workspace")
    session_id = active_session_id()

    with st.expander("New workspace"):
        project_name = st.text_input("Project name")
        requirement = st.text_area(
            "Requirement summary",
            height=100,
        )
        create = st.button(
            "Create",
            type="primary",
            disabled=not (session_id and project_name.strip() and requirement.strip()),
        )
    if create:
        try:
            with api_client() as client:
                client.create_session(
                    session_id=session_id,
                    project_name=project_name,
                    requirement_summary=requirement,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
        except ExperienceApiError as error:
            show_api_error(error)
        else:
            st.success("Workspace created.")

    if not session_id:
        st.caption("No active session.")
        return
    try:
        with api_client() as client:
            payload = client.get_workspace(session_id)
    except ExperienceApiError as error:
        show_api_error(error)
        return

    show_viewer_state(payload)
    st.subheader(text_value(payload.get("project_summary")))
    columns = st.columns(4)
    columns[0].metric("Artifacts", len(payload.get("artifact_ids", ())))
    columns[1].metric("Files", integer_value(payload.get("file_count")))
    columns[2].metric("Messages", integer_value(payload.get("message_count")))
    columns[3].metric("Progress", integer_value(payload.get("progress_count")))

    traces = object_list(payload.get("knowledge_traces"))
    if traces:
        st.subheader("Knowledge trace")
        st.dataframe(traces, hide_index=True)
