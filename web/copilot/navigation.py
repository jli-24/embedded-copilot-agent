from __future__ import annotations

import streamlit as st

from web.copilot.app_pages import (
    blueprint,
    chat,
    evidence,
    files,
    model_status,
    progress,
    review,
    upload,
    vision,
    workspace,
)

PAGE_TITLES = (
    "Workspace",
    "Chat",
    "Upload",
    "Vision",
    "Blueprint",
    "Evidence",
    "Files",
    "Progress",
    "Review",
    "Model Status",
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
            upload.render,
            title="Upload",
            icon=":material/attach_file:",
            url_path="upload",
        ),
        st.Page(
            vision.render,
            title="Vision",
            icon=":material/image_search:",
            url_path="vision",
        ),
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
        st.Page(
            model_status.render,
            title="Model Status",
            icon=":material/model_training:",
            url_path="model-status",
        ),
    )
