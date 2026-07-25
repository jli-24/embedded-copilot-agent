from __future__ import annotations

import streamlit as st

from web.copilot.app_pages import (
    blueprint,
    chat,
    evidence,
    files,
    progress,
    review,
    workspace,
)

PAGE_TITLES = (
    "Workspace",
    "Chat",
    "Blueprint",
    "Evidence",
    "Files",
    "Progress",
    "Review",
)


def pages() -> tuple[st.Page, ...]:
    return (
        st.Page(
            workspace.render,
            title="Workspace",
            icon=":material/home:",
            url_path="workspace",
            default=True,
        ),
        st.Page(chat.render, title="Chat", icon=":material/chat:", url_path="chat"),
        st.Page(
            blueprint.render,
            title="Blueprint",
            icon=":material/account_tree:",
            url_path="blueprint",
        ),
        st.Page(
            evidence.render,
            title="Evidence",
            icon=":material/fact_check:",
            url_path="evidence",
        ),
        st.Page(
            files.render,
            title="Files",
            icon=":material/folder:",
            url_path="files",
        ),
        st.Page(
            progress.render,
            title="Progress",
            icon=":material/progress_activity:",
            url_path="progress",
        ),
        st.Page(
            review.render,
            title="Review",
            icon=":material/rate_review:",
            url_path="review",
        ),
    )
