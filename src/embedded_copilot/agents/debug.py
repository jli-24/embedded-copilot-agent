from __future__ import annotations

from typing import Protocol

from embedded_copilot.agents._common import (
    failure_update,
    success_update,
    tool_call_finished,
    tool_call_started,
)
from embedded_copilot.schemas.result import DebugResult, ToolResult, ToolStatus
from embedded_copilot.schemas.state import AgentState
from embedded_copilot.tools.debug_tool import DebugLogInput


class DebugTool(Protocol):
    async def invoke(self, payload: DebugLogInput) -> ToolResult[DebugResult]: ...


def _render_debug(result: DebugResult) -> str:
    evidence = "\n".join(f"- {item}" for item in result.evidence) or "- None captured"
    causes = "\n".join(f"- {item}" for item in result.root_cause)
    solutions = "\n".join(f"- {item}" for item in result.solution)
    next_steps = "\n".join(f"- {item}" for item in result.next_steps)
    return (
        f"Problem Type: {result.problem_type}\n\n"
        f"Evidence:\n{evidence}\n\n"
        f"Root Cause:\n{causes}\n\n"
        f"Confidence: {result.confidence}\n\n"
        f"Recommendation:\n{solutions}\n\n"
        f"Next Steps:\n{next_steps}"
    )


class DebugAgent:
    def __init__(self, *, tool: DebugTool) -> None:
        self._tool = tool

    async def run(self, state: AgentState) -> dict[str, object]:
        started_at = tool_call_started(state, tool_name="debug_log_tool")
        tool_result = await self._tool.invoke(
            DebugLogInput(log=state["user_input"])
        )
        tool_call_finished(
            state,
            tool_name="debug_log_tool",
            started_at=started_at,
            error=tool_result.error,
        )
        if tool_result.status is ToolStatus.ERROR:
            assert tool_result.error is not None
            return failure_update(state, error=tool_result.error)
        assert tool_result.data is not None
        return success_update(
            state,
            result=tool_result.data,
            final_answer=_render_debug(tool_result.data),
        )
