from __future__ import annotations

from typing import get_type_hints

import pytest
from pydantic import ValidationError

from embedded_copilot.schemas.api import ChatRequest, ChatResponse
from embedded_copilot.schemas.result import (
    DebugResult,
    FirmwareResult,
    KnowledgeResult,
    SourceCitation,
)
from embedded_copilot.schemas.state import AgentState, Intent


def test_chat_request_strips_message() -> None:
    request = ChatRequest(message="  ESP32 如何配置 SPI？  ")

    assert request.message == "ESP32 如何配置 SPI？"


def test_chat_request_rejects_blank_message() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(message="   ")


def test_source_citation_uses_one_based_pages() -> None:
    with pytest.raises(ValidationError):
        SourceCitation(
            source="knowledge/manual.pdf",
            filename="manual.pdf",
            page=0,
            chunk_id="chunk-1",
            score=0.8,
        )


def test_agent_state_declares_approved_contract() -> None:
    fields = get_type_hints(AgentState)

    assert set(fields) == {
        "trace_id",
        "user_input",
        "intent",
        "selected_agents",
        "messages",
        "results",
        "sources",
        "errors",
        "final_answer",
        "status",
    }
    assert set(Intent) == {
        Intent.KNOWLEDGE,
        Intent.FIRMWARE,
        Intent.DEBUG,
        Intent.UNKNOWN,
    }


def test_chat_response_accepts_each_specialist_result() -> None:
    citation = SourceCitation(
        source="knowledge/embedded_basics.md",
        filename="embedded_basics.md",
        page=None,
        chunk_id="chunk-1",
        score=0.9,
    )
    results = [
        KnowledgeResult(answer="SPI uses a clocked bus.", sources=[citation]),
        FirmwareResult(
            language="C",
            platform="ESP-IDF",
            code="void app_main(void) {}",
            explanation="Minimal entry point.",
            limitations=["Not hardware tested."],
        ),
        DebugResult(
            problem_type="ESP32 Guru Meditation",
            evidence=["Guru Meditation Error"],
            root_cause=["The exception type is not present in the excerpt."],
            confidence="low",
            solution=["Capture the complete panic output."],
            next_steps=["Provide the Backtrace line."],
        ),
    ]

    for result in results:
        response = ChatResponse(
            answer="answer",
            agents_used=[result.kind],
            sources=[citation] if result.kind == "knowledge" else [],
            trace_id="trace-1",
            result=result,
        )
        assert response.result == result
