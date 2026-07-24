from __future__ import annotations

from embedded_copilot.agents.types import AgentResult, AgentStatus
from embedded_copilot.benchmark.models import BenchmarkTrace
from embedded_copilot.benchmark.trace import TraceCollector


class _Clock:
    def __init__(self, *values: float) -> None:
        self._values = iter(values)

    def __call__(self) -> float:
        return next(self._values)


def test_trace_collector_observes_supervisor_order_and_handoffs() -> None:
    collector = TraceCollector(clock=_Clock(10.0, 10.025))
    started_at = collector.start()
    result = AgentResult(
        agent_name="SupervisorAgent",
        status=AgentStatus.ERROR,
        output="safe supervisor result",
        metadata={
            "supervisor_plan": {
                "project_name": "demo",
                "tasks": [
                    {"agent_name": "FirmwareAgent", "task": "firmware"},
                    {"agent_name": "HardwareAgent", "task": "hardware"},
                    {"agent_name": "PCBAgent", "task": "pcb"},
                ],
                "rationale": "synthetic plan",
            },
            "agent_results": [
                {
                    "agent_name": "FirmwareAgent",
                    "status": "success",
                    "output": "redacted by observer",
                },
                {
                    "agent_name": "HardwareAgent",
                    "status": "error",
                    "output": "redacted by observer",
                },
                {
                    "agent_name": "PCBAgent",
                    "status": "success",
                    "output": "redacted by observer",
                },
            ],
        },
    )

    trace = collector.collect(
        case_id="chain",
        target_name="SupervisorAgent",
        result=result,
        started_at=started_at,
        execution_succeeded=True,
    )

    assert isinstance(trace, BenchmarkTrace)
    assert [(event.event_type, event.target, event.status) for event in trace.events] == [
        ("agent_call", "FirmwareAgent", "success"),
        ("handoff", "HardwareAgent", "error"),
        ("agent_call", "HardwareAgent", "error"),
        ("handoff", "PCBAgent", "error"),
        ("agent_call", "PCBAgent", "success"),
    ]
    assert trace.events[1].handoff_from == "FirmwareAgent"
    assert trace.events[1].handoff_to == "HardwareAgent"
    assert trace.execution_metrics.execution_time_ms == 25.0
    assert trace.execution_metrics.agent_calls == 3
    assert trace.execution_metrics.knowledge_calls == 0
    assert "redacted by observer" not in trace.model_dump_json()


def test_trace_collector_records_single_agent_and_knowledge_calls() -> None:
    agent_collector = TraceCollector(clock=_Clock(1.0, 1.001))
    agent_start = agent_collector.start()
    agent_trace = agent_collector.collect(
        case_id="firmware",
        target_name="FirmwareAgent",
        result=AgentResult(
            agent_name="FirmwareAgent",
            status=AgentStatus.SUCCESS,
            output="private generated source",
        ),
        started_at=agent_start,
        execution_succeeded=True,
    )
    knowledge_collector = TraceCollector(clock=_Clock(2.0, 2.002))
    knowledge_start = knowledge_collector.start()
    knowledge_trace = knowledge_collector.collect(
        case_id="knowledge",
        target_name="KnowledgeGateway",
        result=[],
        started_at=knowledge_start,
        execution_succeeded=True,
    )

    assert agent_trace.execution_metrics.agent_calls == 1
    assert agent_trace.events[0].event_type == "agent_call"
    assert knowledge_trace.execution_metrics.knowledge_calls == 1
    assert knowledge_trace.events[0].event_type == "knowledge_call"


def test_trace_collector_marks_execution_failure_without_exception_content() -> None:
    collector = TraceCollector(clock=_Clock(3.0, 3.0))
    started_at = collector.start()

    trace = collector.collect(
        case_id="failed",
        target_name="DebugAgent",
        result=None,
        started_at=started_at,
        execution_succeeded=False,
    )

    assert trace.events[0].status == "error"
    assert trace.events[0].metadata == {}


def test_trace_collector_observes_one_supervisor_gateway_call() -> None:
    collector = TraceCollector(clock=_Clock(4.0, 4.001))
    started_at = collector.start()
    result = AgentResult(
        agent_name="SupervisorAgent",
        status=AgentStatus.SUCCESS,
        output="safe supervisor result",
        metadata={
            "supervisor_plan": {
                "tasks": [{"agent_name": "FirmwareAgent"}],
            },
            "agent_results": [
                {"agent_name": "FirmwareAgent", "status": "success"},
            ],
            "execution_summary": {
                "metadata": {
                    "supervisor_trace": [
                        {
                            "stage": "gateway_retrieved",
                            "status": "success",
                            "target": "KnowledgeGateway",
                            "domains": ["firmware"],
                            "count": 1,
                        }
                    ]
                }
            },
        },
    )

    trace = collector.collect(
        case_id="gateway-chain",
        target_name="SupervisorAgent",
        result=result,
        started_at=started_at,
        execution_succeeded=True,
    )

    assert trace.execution_metrics.knowledge_calls == 1
    assert [(event.event_type, event.target) for event in trace.events] == [
        ("knowledge_call", "KnowledgeGateway"),
        ("agent_call", "FirmwareAgent"),
    ]
    assert [event.sequence for event in trace.events] == [1, 2]
