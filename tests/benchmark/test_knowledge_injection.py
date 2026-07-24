from __future__ import annotations

import json
from pathlib import Path

from embedded_copilot.benchmark.datasets.synthetic import (
    create_synthetic_knowledge_injection_dataset,
    create_synthetic_provider_integration_dataset,
)
from embedded_copilot.benchmark.runner import BenchmarkRunner
from embedded_copilot.benchmark.trace import TraceCollector
from embedded_copilot.knowledge.gateway import KnowledgeGateway
from embedded_copilot.knowledge.models import KnowledgeQuery, KnowledgeResult
from embedded_copilot.knowledge.providers.local import LocalKnowledgeProvider
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


class CountingKnowledgeGateway(KnowledgeGateway):
    def __init__(self, provider: LocalKnowledgeProvider) -> None:
        super().__init__([provider])
        self.calls = 0

    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        self.calls += 1
        return super().search(query)


def test_benchmark_observes_real_local_provider_gateway_chain(
    tmp_path: Path,
) -> None:
    firmware = tmp_path / "firmware"
    firmware.mkdir()
    (firmware / "camera.json").write_text(
        json.dumps(
            {
                "id": "synthetic-camera-reference",
                "title": "Synthetic ESP32 camera reference",
                "content": "Synthetic ESP32 camera firmware guidance.",
                "category": "camera",
                "domain": "firmware",
                "score": 0.9,
            }
        ),
        encoding="utf-8",
    )
    gateway = CountingKnowledgeGateway(
        LocalKnowledgeProvider(knowledge_root=tmp_path)
    )
    collector = RecordingTraceCollector()

    report = BenchmarkRunner(
        {"SupervisorAgent": SupervisorAgent(knowledge_gateway=gateway)},
        trace_collector=collector,
    ).run(create_synthetic_provider_integration_dataset())

    assert report.passed_cases == 1
    assert report.failed_cases == 0
    assert gateway.calls == 1
    assert collector.traces[0].execution_metrics.knowledge_calls == 1
