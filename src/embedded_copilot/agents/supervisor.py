from __future__ import annotations

import logging
import re

from pydantic import Field

from embedded_copilot.schemas.result import ContractModel
from embedded_copilot.schemas.state import (
    AgentName,
    AgentState,
    Intent,
    WorkflowStatus,
)


class RoutingDecision(ContractModel):
    intent: Intent
    reason: str = Field(min_length=1)


_DEBUG_MARKERS = (
    "guru meditation",
    "hardfault",
    "hard fault",
    "backtrace",
    "panic",
    "serial log",
    "编译错误",
    "报错",
    "崩溃",
    "日志分析",
)
_FIRMWARE_ACTION_MARKERS = (
    "生成",
    "编写",
    "解释",
    "架构",
    "优化",
    "generate",
    "write",
    "create",
    "implement",
    "explain",
    "architecture",
    "optimize",
)
_FIRMWARE_OBJECT_PATTERN = re.compile(
    r"(?:c\+*\+?|code|firmware|esp-idf|stm32\s*hal|freertos|代码|任务)",
    re.IGNORECASE,
)
_KNOWLEDGE_MARKERS = (
    "esp32",
    "stm32",
    "freertos",
    "uart",
    "spi",
    "i2c",
    "datasheet",
    "数据手册",
    "如何配置",
    "是什么",
)


def classify_intent(user_input: str) -> RoutingDecision:
    normalized = user_input.strip().lower()
    if any(marker in normalized for marker in _DEBUG_MARKERS) or "error:" in normalized:
        return RoutingDecision(
            intent=Intent.DEBUG,
            reason="The request contains failure, panic, compiler, or log evidence.",
        )
    firmware_action = any(marker in normalized for marker in _FIRMWARE_ACTION_MARKERS)
    if firmware_action and _FIRMWARE_OBJECT_PATTERN.search(normalized):
        return RoutingDecision(
            intent=Intent.FIRMWARE,
            reason="The request explicitly asks for code, explanation, or architecture.",
        )
    if any(marker in normalized for marker in _KNOWLEDGE_MARKERS):
        return RoutingDecision(
            intent=Intent.KNOWLEDGE,
            reason="The request is an embedded knowledge or documentation question.",
        )
    return RoutingDecision(
        intent=Intent.UNKNOWN,
        reason="The request does not contain enough v0.1 routing context.",
    )


def supervisor_node(state: AgentState) -> dict[str, object]:
    decision = classify_intent(state["user_input"])
    agent_by_intent = {
        Intent.KNOWLEDGE: AgentName.KNOWLEDGE,
        Intent.FIRMWARE: AgentName.FIRMWARE,
        Intent.DEBUG: AgentName.DEBUG,
    }
    selected = agent_by_intent.get(decision.intent)
    if selected is not None:
        logging.getLogger("embedded_copilot.workflow").info(
            "agent_selected",
            extra={
                "event_name": "agent_selected",
                "trace_id": state["trace_id"],
                "agent_name": selected.value,
            },
        )
    return {
        "intent": decision.intent,
        "selected_agents": [selected] if selected is not None else [],
        "status": (
            WorkflowStatus.RUNNING
            if selected is not None
            else WorkflowStatus.NEEDS_CLARIFICATION
        ),
    }
