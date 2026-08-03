from __future__ import annotations

from collections.abc import Mapping

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error
from web.copilot.client import ExperienceApiError
from web.copilot.reasoning import ReasoningPanel


def render() -> None:
    st.title("Reasoning")
    recommendation_id = st.text_input("Recommendation ID", max_chars=160)
    mode = st.selectbox(
        "Reasoning mode",
        ("EXPLAIN", "COMPARE", "ANALYZE_RISK", "GENERATE_PLAN"),
    )
    question = st.text_area("Question", max_chars=512)
    if not st.button("Ask", type="primary"):
        return
    if not recommendation_id.strip() or not question.strip():
        st.warning("Recommendation ID and a question are required.")
        return
    try:
        with api_client() as client:
            result = ReasoningPanel(client).query(
                recommendation_id=recommendation_id.strip(),
                mode=mode,
                question=question.strip(),
            )
    except ExperienceApiError as error:
        show_api_error(error)
        return
    if not isinstance(result, Mapping):
        show_api_error(ExperienceApiError("Copilot API returned an invalid response."))
        return
    st.subheader("Recommendation")
    st.markdown(str(result.get("summary", "")))
    st.subheader("AI Explanation")
    st.markdown(str(result.get("explanation", "")))
    st.metric("Explanation confidence", str(result.get("confidence", 0.0)))
    st.subheader("Tradeoffs")
    for item in result.get("tradeoffs", ()):
        st.markdown(f"- {item}")
    st.subheader("Risks")
    for item in result.get("risks", ()):
        st.markdown(f"- {item}")
    st.subheader("References")
    for item in result.get("references", ()):
        st.markdown(f"- {item}")
