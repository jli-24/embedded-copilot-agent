from __future__ import annotations

from embedded_copilot.benchmark.datasets.synthetic import (
    create_synthetic_knowledge_injection_dataset,
)
from embedded_copilot.benchmark.runner import BenchmarkRunner
from embedded_copilot.benchmark.trace import TraceCollector
from embedded_copilot.supervisor.agent import SupervisorAgent


class EmptyGateway:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, query):
        self.calls += 1
        return []


class RecordingTraceCollector(TraceCollector):
    def __init__(self) -> None:
        super().__init__()
        self.traces = []

    def collect(self, **kwargs):
        trace = super().collect(**kwargs)
        self.traces.append(trace)
        return trace


def test_benchmark_observes_complete_supervisor_knowledge_injection_chain() -> None:
    gateway = EmptyGateway()
    collector = RecordingTraceCollector()
    supervisor = SupervisorAgent(knowledge_gateway=gateway)  # type: ignore[arg-type]

    report = BenchmarkRunner(
        {"SupervisorAgent": supervisor},
        trace_collector=collector,
    ).run(create_synthetic_knowledge_injection_dataset())

    assert report.passed_cases == 1
    assert report.failed_cases == 0
    assert gateway.calls == 1
    assert len(collector.traces) == 1
    trace = collector.traces[0]
    assert trace.execution_metrics.agent_calls == 4
    assert trace.execution_metrics.knowledge_calls == 1
