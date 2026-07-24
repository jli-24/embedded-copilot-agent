from __future__ import annotations

from embedded_copilot.benchmark.datasets.synthetic import (
    create_synthetic_github_provider_dataset,
)
from embedded_copilot.benchmark.runner import BenchmarkRunner
from embedded_copilot.benchmark.trace import TraceCollector
from embedded_copilot.agents.types import AgentResult, AgentTask
from embedded_copilot.knowledge.gateway import KnowledgeGateway
from embedded_copilot.knowledge.github.client import FakeGitHubClient
from embedded_copilot.knowledge.github.models import GitHubRepositoryItem
from embedded_copilot.knowledge.providers.github import GitHubKnowledgeProvider
from embedded_copilot.supervisor.agent import SupervisorAgent


class RecordingTraceCollector(TraceCollector):
    def __init__(self) -> None:
        super().__init__()
        self.traces = []

    def collect(self, **kwargs):
        trace = super().collect(**kwargs)
        self.traces.append(trace)
        return trace


class RecordingSupervisor:
    def __init__(self, supervisor: SupervisorAgent) -> None:
        self._supervisor = supervisor
        self.result: AgentResult | None = None

    def run(self, task: AgentTask) -> AgentResult:
        self.result = self._supervisor.run(task)
        return self.result


def _repository() -> GitHubRepositoryItem:
    return GitHubRepositoryItem(
        id="synthetic-github-camera",
        title="Synthetic camera repository",
        repository="synthetic/camera",
        owner="synthetic",
        summary="Synthetic ESP32 camera engineering reference.",
        reference_url="https://github.com/synthetic/camera",
        language="C",
        stars=1,
        score=0.9,
        category="repository",
        domain="firmware",
    )


def test_benchmark_observes_complete_fake_github_provider_chain() -> None:
    client = FakeGitHubClient(
        repositories={
            "ESP32 Camera OV2640 GPIO Power firmware hardware pcb": [
                _repository()
            ]
        }
    )
    collector = RecordingTraceCollector()
    supervisor = RecordingSupervisor(
        SupervisorAgent(
            knowledge_gateway=KnowledgeGateway([GitHubKnowledgeProvider(client)])
        )
    )

    report = BenchmarkRunner(
        {"SupervisorAgent": supervisor},
        trace_collector=collector,
    ).run(create_synthetic_github_provider_dataset())

    assert report.passed_cases == 1
    assert report.failed_cases == 0
    assert client.calls == [
        ("repository", "ESP32 Camera OV2640 GPIO Power firmware hardware pcb"),
        ("code", "ESP32 Camera OV2640 GPIO Power firmware hardware pcb"),
    ]
    assert collector.traces[0].execution_metrics.knowledge_calls == 1
    assert supervisor.result is not None
    execution_summary = supervisor.result.metadata["execution_summary"]
    assert isinstance(execution_summary, dict)
    report_metadata = execution_summary["metadata"]
    assert isinstance(report_metadata, dict)
    supervisor_trace = report_metadata["supervisor_trace"]
    assert isinstance(supervisor_trace, list)
    assert [
        event["count"]
        for event in supervisor_trace
        if event["stage"] == "gateway_retrieved"
    ] == [1]
    assert [
        event["count"]
        for event in supervisor_trace
        if event["stage"] == "context_built"
    ] == [1]

    agent_results = supervisor.result.metadata["agent_results"]
    assert isinstance(agent_results, list)
    firmware_result = next(
        result
        for result in agent_results
        if result["agent_name"] == "FirmwareAgent"
    )
    retrieved = firmware_result["metadata"]["retrieved_documents"]
    assert retrieved == [
        {
            "id": "github:repository:synthetic-github-camera",
            "title": "Synthetic camera repository",
            "source": "GITHUB",
            "category": "repository",
            "score": 0.9,
        }
    ]


def test_client_none_allows_empty_context_supervisor_success() -> None:
    report = BenchmarkRunner(
        {
            "SupervisorAgent": SupervisorAgent(
                knowledge_gateway=KnowledgeGateway([GitHubKnowledgeProvider()])
            )
        }
    ).run(create_synthetic_github_provider_dataset())

    assert report.passed_cases == 1
    assert report.results[0].success is True
    assert report.results[0].metadata["target_name"] == "SupervisorAgent"
