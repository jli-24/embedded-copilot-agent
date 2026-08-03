from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error
from web.copilot.client import ExperienceApiError
from web.copilot.memory import MemoryViewer


def render() -> None:
    st.title("Memory")
    try:
        with api_client() as client:
            candidates = MemoryViewer(client).candidates()
    except ExperienceApiError as error:
        show_api_error(error)
        return
    if not candidates:
        st.info("No memory candidates are available.")
        return
    st.dataframe(candidates, hide_index=True)
    pending = tuple(
        item for item in candidates if item.get("review_status") == "REVIEW_REQUIRED"
    )
    if not pending:
        return
    selected = st.selectbox(
        "Candidate",
        pending,
        format_func=lambda item: str(item.get("memory_id", "")),
    )
    reviewer = st.text_input("Reviewer")
    if st.button("Approve", type="primary", disabled=not reviewer.strip()):
        try:
            with api_client() as client:
                MemoryViewer(client).approve(
                    memory_id=str(selected["memory_id"]),
                    candidate_fingerprint=str(selected["fingerprint"]),
                    reviewer=reviewer.strip(),
                    reviewed_at=datetime.now(UTC).isoformat(),
                )
            st.success("Memory candidate approved.")
        except ExperienceApiError as error:
            show_api_error(error)

