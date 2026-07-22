from __future__ import annotations

from typing import Protocol

from embedded_copilot.agents._common import (
    failure_update,
    success_update,
    tool_call_finished,
    tool_call_started,
)
from embedded_copilot.schemas.result import KnowledgeResult, ToolResult, ToolStatus
from embedded_copilot.schemas.state import AgentState
from embedded_copilot.tools.document_tool import (
    DocumentSearchInput,
    DocumentSearchOutput,
)


class DocumentTool(Protocol):
    async def invoke(
        self,
        payload: DocumentSearchInput,
    ) -> ToolResult[DocumentSearchOutput]: ...


class KnowledgeAgent:
    def __init__(
        self,
        *,
        tool: DocumentTool,
        top_k: int = 4,
        score_threshold: float = 0.15,
    ) -> None:
        self._tool = tool
        self._top_k = top_k
        self._score_threshold = score_threshold

    async def run(self, state: AgentState) -> dict[str, object]:
        started_at = tool_call_started(state, tool_name="document_search_tool")
        tool_result = await self._tool.invoke(
            DocumentSearchInput(
                query=state["user_input"],
                top_k=self._top_k,
                score_threshold=self._score_threshold,
            )
        )
        tool_call_finished(
            state,
            tool_name="document_search_tool",
            started_at=started_at,
            error=tool_result.error,
        )
        if tool_result.status is ToolStatus.ERROR:
            assert tool_result.error is not None
            return failure_update(state, error=tool_result.error)

        assert tool_result.data is not None
        citations = [item.citation for item in tool_result.data.items]
        answer = tool_result.data.answer
        if citations:
            source_lines: list[str] = []
            for item in tool_result.data.items:
                source_line = f"- {item.citation.filename}"
                if item.chapter is not None:
                    source_line += f", chapter {item.chapter}"
                if item.citation.page is not None:
                    source_line += f", page {item.citation.page}"
                source_lines.append(source_line)
            answer = f"{answer}\n\nSources:\n" + "\n".join(source_lines)
        result = KnowledgeResult(
            answer=answer,
            sources=citations,
            insufficient_context=tool_result.data.insufficient_context,
        )
        return success_update(
            state,
            result=result,
            final_answer=answer,
            sources=citations,
        )
