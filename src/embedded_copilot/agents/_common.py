from __future__ import annotations

import logging
from time import perf_counter

from embedded_copilot.schemas.result import AgentResult, ErrorDetail, SourceCitation
from embedded_copilot.schemas.state import AgentState, MessageRecord, WorkflowStatus


logger = logging.getLogger("embedded_copilot.tools")


def tool_call_started(state: AgentState, *, tool_name: str) -> float:
    logger.info(
        "tool_called",
        extra={
            "event_name": "tool_called",
            "trace_id": state["trace_id"],
            "tool_name": tool_name,
        },
    )
    return perf_counter()


def tool_call_finished(
    state: AgentState,
    *,
    tool_name: str,
    started_at: float,
    error: ErrorDetail | None,
) -> None:
    outcome = "error" if error is not None else "success"
    duration_ms = round((perf_counter() - started_at) * 1000, 3)
    logger.info(
        "tool_completed",
        extra={
            "event_name": "tool_completed",
            "trace_id": state["trace_id"],
            "tool_name": tool_name,
            "outcome": outcome,
            "duration_ms": duration_ms,
        },
    )
    if error is not None:
        logger.error(
            "error_occurred",
            extra={
                "event_name": "error_occurred",
                "trace_id": state["trace_id"],
                "tool_name": tool_name,
                "error_category": error.code.value,
            },
        )


def success_update(
    state: AgentState,
    *,
    result: AgentResult,
    final_answer: str,
    sources: list[SourceCitation] | None = None,
) -> dict[str, object]:
    return {
        "results": [*state["results"], result],
        "sources": [*state["sources"], *(sources or [])],
        "messages": [
            *state["messages"],
            MessageRecord(role="assistant", content=final_answer),
        ],
        "final_answer": final_answer,
        "status": WorkflowStatus.COMPLETED,
    }


def failure_update(
    state: AgentState,
    *,
    error: ErrorDetail,
) -> dict[str, object]:
    return {
        "errors": [*state["errors"], error],
        "messages": [
            *state["messages"],
            MessageRecord(role="assistant", content=error.message),
        ],
        "final_answer": error.message,
        "status": WorkflowStatus.FAILED,
    }
