from __future__ import annotations

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error, show_viewer_state
from web.copilot.client import ExperienceApiError
from web.copilot.contracts import object_list
from web.copilot.state import active_session_id

DISPLAY_COLUMNS = (
    "file_id",
    "basename",
    "file_type",
    "size",
    "source",
    "status",
    "timestamp",
)


def render() -> None:
    st.title("Files")
    session_id = active_session_id()
    if not session_id:
        st.caption("No active session.")
        return
    try:
        with api_client() as client:
            payload = client.get_files(session_id)
    except ExperienceApiError as error:
        show_api_error(error)
        return

    show_viewer_state(payload)
    rows = tuple(
        {column: item.get(column) for column in DISPLAY_COLUMNS}
        for item in object_list(payload.get("files"))
    )
    if rows:
        st.dataframe(rows, hide_index=True)
