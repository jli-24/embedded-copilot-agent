from __future__ import annotations

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error, show_viewer_state
from web.copilot.client import ExperienceApiError
from web.copilot.contracts import integer_value, object_list, text_value
from web.copilot.state import active_session_id


def render() -> None:
    st.title("Progress")
    session_id = active_session_id()
    if not session_id:
        st.caption("No active session.")
        return
    try:
        with api_client() as client:
            payload = client.get_progress(session_id)
    except ExperienceApiError as error:
        show_api_error(error)
        return

    show_viewer_state(payload)
    for item in object_list(payload.get("items")):
        stage = text_value(item.get("stage"))
        status = text_value(item.get("status"))
        summary = text_value(item.get("summary"))
        percent = min(integer_value(item.get("percent")), 100)
        st.write(f"**{stage}** · {status}")
        if item.get("is_error") is True:
            st.error(summary)
        st.progress(percent, text=summary)
