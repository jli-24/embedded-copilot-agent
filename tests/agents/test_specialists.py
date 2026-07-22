from __future__ import annotations

import asyncio
from copy import deepcopy

from embedded_copilot.agents.debug import DebugAgent
from embedded_copilot.agents.firmware import FirmwareAgent
from embedded_copilot.agents.knowledge import KnowledgeAgent
from embedded_copilot.agents.workflow import create_initial_state
from embedded_copilot.schemas.result import (
    DebugResult,
    ErrorCode,
    ErrorDetail,
    FirmwareResult,
    SourceCitation,
    ToolResult,
    ToolStatus,
)
from embedded_copilot.schemas.state import WorkflowStatus
from embedded_copilot.tools.document_tool import (
    DocumentSearchOutput,
    RetrievedItem,
)


class StaticTool:
    def __init__(self, result: object) -> None:
        self.result = result
        self.payloads: list[object] = []

    async def invoke(self, payload: object) -> object:
        self.payloads.append(payload)
        return self.result


def test_knowledge_agent_preserves_citations_without_mutating_state() -> None:
    citation = SourceCitation(
        source="knowledge/embedded_basics.md",
        filename="embedded_basics.md",
        page=None,
        chunk_id="spi",
        score=0.9,
    )
    tool = StaticTool(
        ToolResult[DocumentSearchOutput](
            status=ToolStatus.SUCCESS,
            data=DocumentSearchOutput(
                answer="ESP32 SPI configuration requires mode and clock.",
                items=[
                    RetrievedItem(
                        chunk_id="spi",
                        text="context",
                        citation=citation,
                    )
                ],
            ),
        )
    )
    state = create_initial_state("ESP32如何配置SPI？", trace_id="trace-1")
    original = deepcopy(state)

    update = asyncio.run(KnowledgeAgent(tool=tool).run(state))

    assert state == original
    assert update["sources"] == [citation]
    assert update["results"][0].kind == "knowledge"
    assert update["status"] is WorkflowStatus.COMPLETED


def test_firmware_agent_returns_structured_code() -> None:
    firmware = FirmwareResult(
        language="C",
        platform="ESP-IDF",
        code="void app_main(void) {}",
        explanation="Example.",
        limitations=["Not hardware tested."],
    )
    tool = StaticTool(
        ToolResult[FirmwareResult](status=ToolStatus.SUCCESS, data=firmware)
    )
    state = create_initial_state(
        "生成ESP32 FreeRTOS LED任务",
        trace_id="trace-1",
    )

    update = asyncio.run(FirmwareAgent(tool=tool).run(state))

    assert update["results"] == [firmware]
    assert update["final_answer"] == firmware.explanation
    assert update["status"] is WorkflowStatus.COMPLETED


def test_debug_agent_returns_evidence_labeled_result() -> None:
    debug = DebugResult(
        problem_type="ESP32 Guru Meditation",
        evidence=["Guru Meditation Error"],
        root_cause=["Invalid memory access is inferred."],
        confidence="low",
        solution=["Decode the Backtrace."],
        next_steps=["Provide the ELF file."],
    )
    tool = StaticTool(ToolResult[DebugResult](status=ToolStatus.SUCCESS, data=debug))
    state = create_initial_state("Guru Meditation Error", trace_id="trace-1")

    update = asyncio.run(DebugAgent(tool=tool).run(state))

    assert update["results"] == [debug]
    assert "Evidence" in update["final_answer"]
    assert "Root Cause" in update["final_answer"]


def test_specialist_maps_tool_error_to_failed_state() -> None:
    error = ErrorDetail(
        code=ErrorCode.TIMEOUT,
        message="Tool timed out.",
        retryable=True,
    )
    tool = StaticTool(
        ToolResult[DocumentSearchOutput](status=ToolStatus.ERROR, error=error)
    )
    state = create_initial_state("ESP32 SPI", trace_id="trace-1")

    update = asyncio.run(KnowledgeAgent(tool=tool).run(state))

    assert update["errors"] == [error]
    assert update["status"] is WorkflowStatus.FAILED
