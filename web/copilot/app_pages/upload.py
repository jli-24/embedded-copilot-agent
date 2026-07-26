from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error
from web.copilot.client import ExperienceApiError
from web.copilot.state import (
    active_session_id,
    attachment_receipt,
    store_attachment_receipt,
)


def render() -> None:
    st.title("Upload")
    session_id = active_session_id()
    st.caption("Register reference metadata only. No file payload is uploaded.")
    if not session_id:
        st.info("Enter a session ID to register a reference.")
        return

    existing = attachment_receipt(session_id)
    if existing is not None:
        st.success("Reference metadata registered.")
        st.write(existing)

    with st.form("attachment_reference_form"):
        reference_id = st.text_input(
            "Reference ID",
            placeholder="image:schematic-1",
        )
        input_type = st.selectbox("Reference type", ("IMAGE", "FILE"))
        basename = st.text_input("Basename", placeholder="schematic.png")
        summary = st.text_area(
            "Reference summary",
            max_chars=512,
            placeholder="Describe the referenced engineering material.",
        )
        size_bytes = st.number_input(
            "Size in bytes",
            min_value=0,
            step=1,
        )
        submitted = st.form_submit_button(
            "Register reference",
            icon=":material/attach_file:",
        )
    if not submitted:
        return

    try:
        with api_client() as client:
            receipt = client.bind_attachment(
                session_id,
                reference_id=reference_id,
                input_type=input_type,
                basename=basename,
                summary=summary,
                size_bytes=int(size_bytes),
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        store_attachment_receipt(session_id, receipt)
    except (ExperienceApiError, ValueError) as error:
        show_api_error(ExperienceApiError(str(error)))
        return
    st.rerun()
