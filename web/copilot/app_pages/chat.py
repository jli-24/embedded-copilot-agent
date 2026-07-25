from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error
from web.copilot.client import ExperienceApiError
from web.copilot.contracts import text_value
from web.copilot.state import (
    active_session_id,
    conversation_result,
    store_conversation_result,
)


def render() -> None:
    st.title("Chat")
    session_id = active_session_id()
    if session_id:
        answer_summary, handoff = conversation_result(session_id)
        if answer_summary is not None:
            with st.chat_message("assistant"):
                st.write(answer_summary)
                if handoff is not None:
                    st.caption(handoff)

    prompt = st.chat_input(
        "Message",
        disabled=not session_id,
        max_chars=512,
        submit_mode="disable",
    )
    if not prompt:
        return
    with st.chat_message("user"):
        st.write(prompt)
    try:
        with api_client() as client:
            result = client.send_message(
                session_id,
                message_id=f"message:{uuid4().hex}",
                summary=prompt,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
    except ExperienceApiError as error:
        show_api_error(error)
        return
    answer_summary = text_value(result.get("answer_summary"), fallback="")
    handoff = text_value(result.get("handoff"), fallback="")
    if not answer_summary or not handoff:
        show_api_error(ExperienceApiError("Copilot API returned an invalid response."))
        return
    store_conversation_result(
        session_id,
        answer_summary=answer_summary,
        handoff=handoff,
    )
    st.rerun()
