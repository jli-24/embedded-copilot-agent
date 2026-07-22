from __future__ import annotations

import re
from typing import Protocol

from embedded_copilot.agents._common import (
    failure_update,
    success_update,
    tool_call_finished,
    tool_call_started,
)
from embedded_copilot.schemas.result import FirmwareResult, ToolResult, ToolStatus
from embedded_copilot.schemas.state import AgentState
from embedded_copilot.tools.code_tool import (
    CodeAnalysisInput,
    CodeOperation,
)


class CodeTool(Protocol):
    async def invoke(
        self,
        payload: CodeAnalysisInput,
    ) -> ToolResult[FirmwareResult]: ...


def _operation(user_input: str) -> CodeOperation:
    lowered = user_input.lower()
    if "解释" in user_input or "explain" in lowered:
        return CodeOperation.EXPLAIN
    if "架构" in user_input or "architecture" in lowered:
        return CodeOperation.ARCHITECTURE
    return CodeOperation.GENERATE


def _extract_code(user_input: str) -> str | None:
    match = re.search(r"```(?:c|cpp|c\+\+)?\s*(.*?)```", user_input, re.DOTALL)
    return match.group(1).strip() if match else None


def _platform(user_input: str) -> str:
    lowered = user_input.lower()
    if "esp32" in lowered or "esp-idf" in lowered:
        return "ESP-IDF"
    if "stm32" in lowered or "hal" in lowered:
        return "STM32 HAL"
    if "freertos" in lowered:
        return "FreeRTOS"
    return "generic embedded"


class FirmwareAgent:
    def __init__(self, *, tool: CodeTool) -> None:
        self._tool = tool

    async def run(self, state: AgentState) -> dict[str, object]:
        operation = _operation(state["user_input"])
        code = _extract_code(state["user_input"])
        if operation is CodeOperation.EXPLAIN and code is None:
            code = state["user_input"]
        started_at = tool_call_started(state, tool_name="code_analysis_tool")
        tool_result = await self._tool.invoke(
            CodeAnalysisInput(
                operation=operation,
                request=state["user_input"],
                code=code,
                language="C++" if "c++" in state["user_input"].lower() else "C",
                platform=_platform(state["user_input"]),
            )
        )
        tool_call_finished(
            state,
            tool_name="code_analysis_tool",
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
            final_answer=tool_result.data.explanation,
        )
