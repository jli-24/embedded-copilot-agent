from __future__ import annotations

from collections.abc import Mapping

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error
from web.copilot.client import ExperienceApiError


def render() -> None:
    st.title("Engineering Intelligence")
    with st.form("engineering_intelligence_form"):
        project_id = st.text_input("Project ID", max_chars=160)
        question = st.text_area("Engineering question", max_chars=512)
        submitted = st.form_submit_button("Analyze", type="primary")
    if not submitted:
        return
    if not project_id.strip() or not question.strip():
        st.warning("Project ID and an engineering question are required.")
        return
    try:
        with api_client() as client:
            payload = client.query_intelligence(
                project_id=project_id.strip(),
                question=question.strip(),
            )
    except ExperienceApiError as error:
        show_api_error(error)
        return
    result = payload.get("result")
    if not isinstance(result, Mapping):
        show_api_error(ExperienceApiError("Copilot API returned an invalid response."))
        return
    recommendation = result.get("recommendation")
    knowledge = result.get("knowledge_context")
    if not isinstance(recommendation, Mapping) or not isinstance(knowledge, Mapping):
        show_api_error(ExperienceApiError("Copilot API returned an invalid response."))
        return
    st.subheader("Recommendation")
    st.markdown(str(recommendation.get("summary", "")))
    st.metric("Confidence", str(recommendation.get("confidence", 0.0)))
    st.subheader("Evidence")
    evidence = knowledge.get("evidence", ())
    if isinstance(evidence, (tuple, list)):
        st.dataframe(
            tuple(
                {
                    "evidence_id": item.get("evidence_id", ""),
                    "source_type": item.get("source_type", ""),
                    "reference_id": item.get("reference_id", ""),
                    "summary": item.get("summary", ""),
                    "confidence": item.get("confidence", 0.0),
                }
                for item in evidence
                if isinstance(item, Mapping)
            ),
            hide_index=True,
        )
    st.subheader("Risks")
    for risk in recommendation.get("risks", ()):
        st.markdown(f"- {risk}")
    st.warning(
        "This is a deterministic engineering proposal. Engineer validation is required."
    )
