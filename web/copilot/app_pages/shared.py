from __future__ import annotations

import os

import streamlit as st

from web.copilot.client import CopilotExperienceClient, ExperienceApiError

API_URL = os.getenv("EMBEDDED_COPILOT_API_URL", "http://127.0.0.1:8765")


def api_client() -> CopilotExperienceClient:
    return CopilotExperienceClient(API_URL)


def show_api_error(error: ExperienceApiError) -> None:
    st.error(str(error))


def show_viewer_state(payload: dict[str, object]) -> None:
    raw = payload.get("viewer_state")
    state = raw if isinstance(raw, dict) else {}
    status = state.get("status")
    detail = state.get("detail")
    if status == "EMPTY":
        st.info(detail if isinstance(detail, str) else "No projected data.")
    elif status == "UNAVAILABLE":
        st.warning(detail if isinstance(detail, str) else "Projection unavailable.")
