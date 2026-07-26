from __future__ import annotations

import streamlit as st


def render() -> None:
    st.title("Model Status")
    st.caption(
        "Foundation status only. No production provider connection is configured."
    )
    st.table(
        (
            {"Provider": "Mock Provider", "Status": "Test only"},
            {"Provider": "OpenAI", "Status": "Unavailable"},
            {"Provider": "DeepSeek", "Status": "Unavailable"},
            {"Provider": "Ollama", "Status": "Unavailable"},
        )
    )
