from __future__ import annotations

from collections.abc import Mapping, Sequence

import streamlit as st

SESSION_ID_KEY = "session_id"
ANSWER_SUMMARY_KEY = "answer_summary"
HANDOFF_KEY = "handoff"
REVIEW_RECEIPT_KEY = "review_receipt"
ATTACHMENT_RECEIPT_KEY = "attachment_receipt"
VISION_SUGGESTION_KEY = "vision_suggestion"
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


def store_attachment_receipt(
    session_id: str,
    receipt: Mapping[str, object],
) -> dict[str, object]:
    identifier = _safe_text(session_id, field="session_id")
    receipt_session_id = _safe_text(
        receipt.get("session_id"),
        field="receipt.session_id",
    )
    if receipt_session_id.casefold() != identifier.casefold():
        raise ValueError("attachment receipt session identity is inconsistent")
    projected: dict[str, object] = {
        field: _safe_text(receipt.get(field), field=f"receipt.{field}")
        for field in (
            "session_id",
            "reference_id",
            "type",
            "basename",
            "summary",
            "status",
            "created_at",
        )
    }
    size = receipt.get("size_bytes")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise ValueError("receipt.size_bytes is invalid")
    projected["size_bytes"] = size
    st.session_state[ATTACHMENT_RECEIPT_KEY] = projected
    return dict(projected)


def attachment_receipt(session_id: str) -> dict[str, object] | None:
    return _bound_mapping(ATTACHMENT_RECEIPT_KEY, session_id)


def store_vision_suggestion(
    session_id: str,
    suggestion: Mapping[str, object],
) -> dict[str, str]:
    identifier = _safe_text(session_id, field="session_id")
    projected = {
        "session_id": identifier,
        "type": _safe_text(suggestion.get("type"), field="suggestion.type"),
        "summary": _safe_text(
            suggestion.get("summary"),
            field="suggestion.summary",
        ),
    }
    reference_id = suggestion.get("reference_id")
    if reference_id is not None:
        projected["reference_id"] = _safe_text(
            reference_id,
            field="suggestion.reference_id",
        )
    st.session_state[VISION_SUGGESTION_KEY] = projected
    return dict(projected)


def vision_suggestion(session_id: str) -> dict[str, object] | None:
    return _bound_mapping(VISION_SUGGESTION_KEY, session_id)


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


def _bound_mapping(key: str, session_id: str) -> dict[str, object] | None:
    identifier = _safe_text(session_id, field="session_id")
    value = st.session_state.get(key)
    if not isinstance(value, Mapping):
        return None
    value_session_id = value.get("session_id")
    if (
        not isinstance(value_session_id, str)
        or value_session_id.casefold() != identifier.casefold()
    ):
        return None
    return {
        str(item_key): item
        for item_key, item in value.items()
        if isinstance(item_key, str)
        and (
            isinstance(item, str)
            or (isinstance(item, int) and not isinstance(item, bool))
        )
    }


def _safe_text(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    candidate = " ".join(value.split())[:MAX_STATE_TEXT_LENGTH]
    if not candidate:
        raise ValueError(f"{field} is empty")
    return candidate
