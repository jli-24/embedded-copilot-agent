from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error, show_viewer_state
from web.copilot.client import ExperienceApiError
from web.copilot.contracts import object_list, text_value
from web.copilot.state import (
    active_session_id,
    review_receipt,
    store_review_receipt,
)


def render() -> None:
    st.title("Review")
    st.caption("AI Proposal → Engineer Review")
    st.warning("记录用户意图，不代表 Artifact 已批准")
    session_id = active_session_id()
    if not session_id:
        st.caption("No active session.")
        return
    existing_receipt = review_receipt(session_id)
    if existing_receipt is not None:
        st.success(
            f"{text_value(existing_receipt.get('status'))}: "
            f"{text_value(existing_receipt.get('handoff'))}"
        )
    try:
        with api_client() as client:
            payload = client.get_artifacts(session_id)
    except ExperienceApiError as error:
        show_api_error(error)
        return

    show_viewer_state(payload)
    artifact_ids = tuple(
        text_value(item.get("artifact_id"), fallback="")
        for item in object_list(payload.get("artifacts"))
    )
    artifact_ids = tuple(item for item in artifact_ids if item)
    if not artifact_ids:
        st.info("No ArtifactView is available for review.")
        return

    artifact_id = st.selectbox("Artifact", artifact_ids)
    comment = st.text_area("Comment summary")
    with st.container(horizontal=True):
        request_review = st.button("Request Review")
        approve_intent = st.button("Approve Intent", type="primary")
        request_change = st.button("Request Change")
    action = next(
        (
            value
            for selected, value in (
                (request_review, "REQUEST_REVIEW"),
                (approve_intent, "APPROVE_INTENT"),
                (request_change, "REQUEST_CHANGE"),
            )
            if selected
        ),
        None,
    )
    if action is None:
        return
    try:
        with api_client() as client:
            receipt = client.record_review(
                session_id,
                intent_id=f"review:{uuid4().hex}",
                artifact_id=artifact_id,
                action=action,
                comment_summary=comment.strip() or None,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
    except ExperienceApiError as error:
        show_api_error(error)
        return
    try:
        safe_receipt = store_review_receipt(session_id, receipt)
    except ValueError:
        show_api_error(ExperienceApiError("Copilot API returned an invalid response."))
        return
    st.success(
        f"{text_value(safe_receipt.get('status'))}: "
        f"{text_value(safe_receipt.get('handoff'))}"
    )
