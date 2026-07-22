from __future__ import annotations

import asyncio

import pytest

from embedded_copilot.agents.debug import DebugAgent
from embedded_copilot.agents.firmware import FirmwareAgent
from embedded_copilot.agents.knowledge import KnowledgeAgent
from embedded_copilot.agents.workflow import build_workflow, create_initial_state
from embedded_copilot.schemas.result import (
    DebugResult,
    FirmwareResult,
    SourceCitation,
    ToolResult,
    ToolStatus,
)
from embedded_copilot.schemas.state import AgentName, WorkflowStatus
from embedded_copilot.tools.document_tool import DocumentSearchOutput, RetrievedItem


class StaticTool:
    def __init__(self, result: object) -> None:
        self.result = result

    async def invoke(self, payload: object) -> object:
        return self.result


def _workflow():
    citation = SourceCitation(
        source="knowledge/embedded_basics.md",
        filename="embedded_basics.md",
        page=None,
        chunk_id="spi",
        score=0.9,
    )
    knowledge_tool = StaticTool(
        ToolResult[DocumentSearchOutput](
            status=ToolStatus.SUCCESS,
            data=DocumentSearchOutput(
                answer="SPI grounded answer",
                items=[
                    RetrievedItem(chunk_id="spi", text="context", citation=citation)
                ],
            ),
        )
    )
    firmware_tool = StaticTool(
        ToolResult[FirmwareResult](
            status=ToolStatus.SUCCESS,
            data=FirmwareResult(
                language="C",
                platform="ESP-IDF",
                code="void app_main(void) {}",
                explanation="Firmware answer",
                limitations=["Not hardware tested."],
            ),
        )
    )
    debug_tool = StaticTool(
        ToolResult[DebugResult](
            status=ToolStatus.SUCCESS,
            data=DebugResult(
                problem_type="ESP32 Guru Meditation",
                evidence=["Guru Meditation Error"],
                root_cause=["Inference"],
                confidence="low",
                solution=["Decode"],
                next_steps=["Provide ELF"],
            ),
        )
    )
    return build_workflow(
        knowledge_agent=KnowledgeAgent(tool=knowledge_tool),
        firmware_agent=FirmwareAgent(tool=firmware_tool),
        debug_agent=DebugAgent(tool=debug_tool),
    )


@pytest.mark.parametrize(
    ("message", "agent"),
    [
        ("ESP32如何配置SPI？", AgentName.KNOWLEDGE),
        ("生成ESP32 FreeRTOS LED任务", AgentName.FIRMWARE),
        ("分析这个Guru Meditation Error", AgentName.DEBUG),
    ],
)
def test_workflow_reaches_exactly_one_specialist(
    message: str,
    agent: AgentName,
) -> None:
    graph = _workflow()

    result = asyncio.run(
        graph.ainvoke(create_initial_state(message, trace_id="trace-1"))
    )

    assert result["selected_agents"] == [agent]
    assert len(result["results"]) == 1
    assert result["status"] is WorkflowStatus.COMPLETED


def test_workflow_returns_clarification_for_unknown_intent() -> None:
    graph = _workflow()

    result = asyncio.run(
        graph.ainvoke(create_initial_state("你好", trace_id="trace-1"))
    )

    assert result["selected_agents"] == []
    assert result["results"][0].kind == "clarification"
    assert result["status"] is WorkflowStatus.NEEDS_CLARIFICATION
