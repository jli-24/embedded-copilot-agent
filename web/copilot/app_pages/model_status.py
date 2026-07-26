from __future__ import annotations

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error
from web.copilot.client import ExperienceApiError
from web.copilot.contracts import text_value


def render() -> None:
    st.title("Model Status")
    st.caption("Request-time status. No background polling or cached availability.")
    try:
        with api_client() as client:
            payload = client.get_model_status()
    except ExperienceApiError as error:
        show_api_error(error)
        return

    provider = text_value(payload.get("provider"))
    status = text_value(payload.get("status"))
    model = text_value(payload.get("model"), fallback="Not configured")
    st.metric("Provider", provider)
    st.metric("Status", status)
    st.metric("Model", model)

    raw_capabilities = payload.get("capabilities")
    if isinstance(raw_capabilities, list):
        labels = tuple(
            text_value(item, fallback="")
            for item in raw_capabilities
            if isinstance(item, str)
        )
    else:
        labels = ()
    st.caption(
        f"Capabilities: {', '.join(item for item in labels if item) or 'None'}"
    )
