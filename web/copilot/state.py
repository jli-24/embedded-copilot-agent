from __future__ import annotations

from collections.abc import Mapping, Sequence

import streamlit as st

SESSION_ID_KEY = "session_id"
ANSWER_SUMMARY_KEY = "answer_summary"
HANDOFF_KEY = "handoff"
REVIEW_RECEIPT_KEY = "review_receipt"
MAX_STATE_TEXT_LENGTH = 512


def active_session_id() -> str:
    value = st.text_input(
        "Session ID",
        key=SESSION_ID_KEY,
        placeholder="session:project",
    )
    return value.strip()


def store_conversation_result(
    session_id: str,
    *,
    answer_summary: str,
    handoff: str,
) -> None:
    identifier = _safe_text(session_id, field="session_id")
    st.session_state[ANSWER_SUMMARY_KEY] = (
        identifier,
        _safe_text(answer_summary, field="answer_summary"),
    )
    st.session_state[HANDOFF_KEY] = (
        identifier,
        _safe_text(handoff, field="handoff"),
    )


def conversation_result(session_id: str) -> tuple[str | None, str | None]:
    identifier = _safe_text(session_id, field="session_id")
    return (
        _bound_text(ANSWER_SUMMARY_KEY, identifier),
        _bound_text(HANDOFF_KEY, identifier),
    )


def store_review_receipt(
    session_id: str,
    receipt: Mapping[str, object],
) -> dict[str, str]:
    identifier = _safe_text(session_id, field="session_id")
    receipt_session_id = _safe_text(
        receipt.get("session_id"),
        field="receipt.session_id",
    )
    if receipt_session_id.casefold() != identifier.casefold():
        raise ValueError("review receipt session identity is inconsistent")
    fields = (
        "intent_id",
        "session_id",
        "artifact_id",
        "action",
        "source",
        "status",
        "handoff",
        "recorded_at",
    )
    projected = {
        field: _safe_text(receipt.get(field), field=f"receipt.{field}")
        for field in fields
    }
    st.session_state[REVIEW_RECEIPT_KEY] = projected
    return dict(projected)


def review_receipt(session_id: str) -> dict[str, str] | None:
    identifier = _safe_text(session_id, field="session_id")
    value = st.session_state.get(REVIEW_RECEIPT_KEY)
    if not isinstance(value, Mapping):
        return None
    receipt_session_id = value.get("session_id")
    if (
        not isinstance(receipt_session_id, str)
        or receipt_session_id.casefold() != identifier.casefold()
    ):
        return None
    return {
        str(key): item
        for key, item in value.items()
        if isinstance(key, str) and isinstance(item, str)
    }


def _bound_text(key: str, session_id: str) -> str | None:
    value = st.session_state.get(key)
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) != 2
        or not all(isinstance(item, str) for item in value)
    ):
        return None
    bound_session_id, text = value
    if bound_session_id.casefold() != session_id.casefold():
        return None
    return text


def _safe_text(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    candidate = " ".join(value.split())[:MAX_STATE_TEXT_LENGTH]
    if not candidate:
        raise ValueError(f"{field} is empty")
    return candidate
