from __future__ import annotations

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error
from web.copilot.client import ExperienceApiError
from web.copilot.contracts import text_value
from web.copilot.state import (
    active_session_id,
    store_vision_suggestion,
    vision_suggestion,
)


def render() -> None:
    st.title("Vision")
    session_id = active_session_id()
    if not session_id:
        st.info("Enter a session ID to analyze a registered image reference.")
        return

    existing = vision_suggestion(session_id)
    if existing is not None:
        _show_suggestion(existing)

    with st.form("vision_reference_form"):
        reference_id = st.text_input(
            "Image reference ID",
            placeholder="image:schematic-1",
        )
        message_summary = st.text_area(
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
                message_summary=message_summary,
            )
        suggestion_type = text_value(result.get("type"), fallback="")
        summary = text_value(result.get("summary"), fallback="")
        if not suggestion_type or not summary:
            raise ExperienceApiError("Copilot API returned an invalid response.")
        store_vision_suggestion(
            session_id,
            {
                "type": suggestion_type,
                "summary": summary,
                "reference_id": reference_id,
            },
        )
    except (ExperienceApiError, ValueError) as error:
        show_api_error(ExperienceApiError(str(error)))
        return
    st.rerun()


def _show_suggestion(suggestion: dict[str, object]) -> None:
    st.subheader("AI Suggestion")
    st.write(suggestion.get("summary", "Suggestion unavailable."))
    reference_id = suggestion.get("reference_id", "Registered image reference")
    st.caption(f"Source Reference: {reference_id}")
    st.warning("Need Engineer Review")
