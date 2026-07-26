from __future__ import annotations

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error
from web.copilot.client import ExperienceApiError
from web.copilot.contracts import text_value
from web.copilot.state import active_session_id


def render() -> None:
    st.title("Vision")
    session_id = active_session_id()
    if not session_id:
        st.info("Enter a session ID to analyze a registered image reference.")
        return

    with st.form("vision_reference_form"):
        reference_id = st.text_input(
            "Image reference ID",
            placeholder="image:schematic-1",
        )
        instruction_summary = st.text_area(
            "Analysis request",
            max_chars=512,
            placeholder="Review the referenced schematic.",
        )
        submitted = st.form_submit_button(
            "Request suggestion",
            icon=":material/image_search:",
        )
    if not submitted:
        return

    try:
        with api_client() as client:
            result = client.analyze_vision(
                session_id,
                reference_id=reference_id,
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
    _show_suggestion(summary, reference_id)


def _show_suggestion(summary: str, reference_id: str) -> None:
    st.subheader("AI Suggestion")
    st.write(summary)
    st.caption(f"Source Reference: {reference_id}")
    st.warning("This output is not Engineering Evidence. Engineer validation required.")
