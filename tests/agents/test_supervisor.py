from __future__ import annotations

import pytest

from embedded_copilot.agents.supervisor import classify_intent, supervisor_node
from embedded_copilot.agents.workflow import create_initial_state
from embedded_copilot.schemas.state import AgentName, Intent, WorkflowStatus


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("ESP32如何配置SPI？", Intent.KNOWLEDGE),
        ("生成ESP32 FreeRTOS LED任务", Intent.FIRMWARE),
        ("分析这个Guru Meditation Error\nBacktrace: 0x40081234", Intent.DEBUG),
        ("请解释这段 C 代码：int value = 1;", Intent.FIRMWARE),
        ("FreeRTOS task 是什么？", Intent.KNOWLEDGE),
        ("How does a FreeRTOS task work?", Intent.KNOWLEDGE),
        ("Generate an ESP32 FreeRTOS task", Intent.FIRMWARE),
    ],
)
def test_classifier_routes_v010_requests(message: str, expected: Intent) -> None:
    decision = classify_intent(message)

    assert decision.intent is expected
    assert decision.reason


def test_unknown_intent_does_not_select_an_agent() -> None:
    state = create_initial_state("你好", trace_id="trace-1")

    update = supervisor_node(state)

    assert update["intent"] is Intent.UNKNOWN
    assert update["selected_agents"] == []
    assert update["status"] is WorkflowStatus.NEEDS_CLARIFICATION


def test_supervisor_selects_exactly_one_specialist() -> None:
    state = create_initial_state("ESP32如何配置SPI？", trace_id="trace-1")

    update = supervisor_node(state)

    assert update["selected_agents"] == [AgentName.KNOWLEDGE]
    assert update["status"] is WorkflowStatus.RUNNING
