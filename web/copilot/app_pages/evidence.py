from __future__ import annotations

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error, show_viewer_state
from web.copilot.client import ExperienceApiError
from web.copilot.contracts import object_list, text_value
from web.copilot.state import active_session_id


def render() -> None:
    st.title("Evidence")
    session_id = active_session_id()
    if not session_id:
        st.caption("No active session.")
        return
    try:
        with api_client() as client:
            payload = client.get_artifacts(session_id)
    except ExperienceApiError as error:
        show_api_error(error)
        return

    show_viewer_state(payload)
    for item in object_list(payload.get("artifacts")):
        st.subheader(text_value(item.get("project_summary")))
        evidence = object_list(item.get("evidence_summary"))
        decisions = object_list(item.get("decision_summary"))
        evidence_tab, decision_tab = st.tabs(("Evidence", "Decisions"))
        with evidence_tab:
            if evidence:
                st.dataframe(evidence, hide_index=True)
            else:
                st.info("No projected evidence.")
        with decision_tab:
            if decisions:
                st.dataframe(decisions, hide_index=True)
            else:
                st.info("No projected decisions.")
