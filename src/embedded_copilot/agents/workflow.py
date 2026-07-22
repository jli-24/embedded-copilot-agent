from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from embedded_copilot.agents.debug import DebugAgent
from embedded_copilot.agents.firmware import FirmwareAgent
from embedded_copilot.agents.knowledge import KnowledgeAgent
from embedded_copilot.agents.supervisor import supervisor_node
from embedded_copilot.schemas.result import ClarificationResult
from embedded_copilot.schemas.state import (
    AgentState,
    Intent,
    MessageRecord,
    WorkflowStatus,
)


def create_initial_state(user_input: str, *, trace_id: str) -> AgentState:
    return AgentState(
        trace_id=trace_id,
        user_input=user_input,
        intent=Intent.UNKNOWN,
        selected_agents=[],
        messages=[MessageRecord(role="user", content=user_input)],
        results=[],
        sources=[],
        errors=[],
        final_answer="",
        status=WorkflowStatus.ROUTING,
    )


def _route(state: AgentState) -> str:
    return state["intent"].value


def _clarification_node(state: AgentState) -> dict[str, object]:
    question = (
        "请说明需要知识检索、Firmware 代码辅助，还是 Debug 日志分析，"
        "并提供 MCU、SDK/HAL 或错误上下文。"
    )
    result = ClarificationResult(
        question=question,
        missing_context=["task type", "target context"],
    )
    return {
        "results": [*state["results"], result],
        "messages": [
            *state["messages"],
            MessageRecord(role="assistant", content=question),
        ],
        "final_answer": question,
        "status": WorkflowStatus.NEEDS_CLARIFICATION,
    }


def _response_node(state: AgentState) -> dict[str, object]:
    return {"status": state["status"]}


def build_workflow(
    *,
    knowledge_agent: KnowledgeAgent,
    firmware_agent: FirmwareAgent,
    debug_agent: DebugAgent,
) -> CompiledStateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("knowledge", knowledge_agent.run)
    graph.add_node("firmware", firmware_agent.run)
    graph.add_node("debug", debug_agent.run)
    graph.add_node("clarification", _clarification_node)
    graph.add_node("response", _response_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        _route,
        {
            Intent.KNOWLEDGE.value: "knowledge",
            Intent.FIRMWARE.value: "firmware",
            Intent.DEBUG.value: "debug",
            Intent.UNKNOWN.value: "clarification",
        },
    )
    for node in ("knowledge", "firmware", "debug", "clarification"):
        graph.add_edge(node, "response")
    graph.add_edge("response", END)
    return graph.compile()
