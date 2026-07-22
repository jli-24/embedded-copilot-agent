from __future__ import annotations

import logging
from typing import Protocol

from embedded_copilot.agents.workflow import create_initial_state
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.schemas.state import AgentState


logger = logging.getLogger(__name__)


class Workflow(Protocol):
    async def ainvoke(self, state: AgentState) -> AgentState: ...


class CopilotService:
    def __init__(self, graph: Workflow) -> None:
        self._graph = graph

    async def chat(self, message: str, *, trace_id: str) -> ChatResponse:
        logger.info(
            "workflow_start",
            extra={"event_name": "workflow_start", "trace_id": trace_id},
        )
        try:
            result: AgentState = await self._graph.ainvoke(
                create_initial_state(message, trace_id=trace_id)
            )
        except Exception:
            logger.error(
                "error_occurred",
                extra={
                    "event_name": "error_occurred",
                    "trace_id": trace_id,
                    "error_category": "workflow_error",
                },
            )
            logger.info(
                "workflow_completed",
                extra={
                    "event_name": "workflow_completed",
                    "trace_id": trace_id,
                    "outcome": "failed",
                },
            )
            raise
        error = result["errors"][-1] if result["errors"] else None
        logger.info(
            "workflow_completed",
            extra={
                "event_name": "workflow_completed",
                "trace_id": trace_id,
                "outcome": result["status"].value,
            },
        )
        return ChatResponse(
            answer=result["final_answer"],
            agents_used=result["selected_agents"],
            sources=result["sources"],
            trace_id=trace_id,
            result=result["results"][-1] if result["results"] else None,
            error=error,
        )
