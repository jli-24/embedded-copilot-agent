from __future__ import annotations

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error
from web.copilot.client import ExperienceApiError
from web.copilot.contracts import text_value
from web.copilot.state import active_session_id


def render() -> None:
    st.title("File Intelligence")
    session_id = active_session_id()
    if not session_id:
        st.info("Enter a session ID to analyze a registered file reference.")
        return

    with st.form("file_intelligence_form"):
        file_id = st.text_input(
            "File reference ID",
            placeholder="file:firmware-1",
        )
        instruction_summary = st.text_area(
            "Analysis request",
            max_chars=512,
            placeholder="Analyze the referenced file structure.",
        )
        submitted = st.form_submit_button(
            "Analyze structure",
            icon=":material/document_scanner:",
        )
    if not submitted:
        return

    try:
        with api_client() as client:
            result = client.analyze_file(
                session_id,
                file_id=file_id,
                instruction_summary=instruction_summary,
            )
        suggestion_type = text_value(result.get("type"), fallback="")
        summary = text_value(result.get("summary"), fallback="")
        if (
            suggestion_type != "reasoning_suggestion"
            or not summary
            or result.get("review_required") is not True
        ):
            raise ExperienceApiError("Copilot API returned an invalid response.")
    except (ExperienceApiError, ValueError) as error:
        show_api_error(ExperienceApiError(str(error)))
        return

    st.subheader("File Reference")
    st.write(file_id)
    st.subheader("AI Suggestion")
    st.write(summary)
    st.warning("This output is not Engineering Evidence. Engineer validation required.")
