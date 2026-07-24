from __future__ import annotations

from collections.abc import Callable

from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.benchmark.dataset import BenchmarkDataset
from embedded_copilot.benchmark.exceptions import BenchmarkRunError
from embedded_copilot.benchmark.models import BenchmarkCase, BenchmarkResult
from embedded_copilot.benchmark.runner import BenchmarkRunner
from embedded_copilot.debug.models import DebugFinding, DebugReport
from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)


class _AgentTarget:
    def __init__(self, name: str, factory: Callable[[AgentTask], AgentResult]) -> None:
        self.name = name
        self._factory = factory
        self.tasks: list[AgentTask] = []

    def run(self, task: AgentTask) -> AgentResult:
        self.tasks.append(task)
        return self._factory(task)


class _KnowledgeTarget:
    def __init__(self) -> None:
        self.queries: list[KnowledgeQuery] = []

    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        self.queries.append(query)
        return [
            KnowledgeResult(
                id="synthetic-doc",
                title="Synthetic document",
                content="PRIVATE KNOWLEDGE BODY",
                source=KnowledgeSource.LOCAL,
                score=1,
            )
        ]


def _debug_case(case_id: str = "debug") -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        name="Synthetic debug",
        category="debug",
        input="synthetic compile marker",
        expected={
            "error_type": "compile_error",
            "finding_ids": ["DBG-COMPILE"],
            "recommendation_keywords": ["include"],
        },
        metadata={"project_name": "synthetic", "nested": {"keep": True}},
    )


def _debug_success(task: AgentTask) -> AgentResult:
    task.metadata["nested"]["keep"] = False  # type: ignore[index]
    report = DebugReport(
        project_name="synthetic",
        error_type="compile_error",
        summary="synthetic report",
        findings=[
            DebugFinding(
                id="DBG-COMPILE",
                category="compile",
                severity="error",
                description="observed synthetic compiler marker",
                evidence=["synthetic marker"],
                recommendation="Check include configuration",
            )
        ],
        recommendations=["Check include configuration"],
    )
    return AgentResult(
        agent_name="DebugAgent",
        status=AgentStatus.SUCCESS,
        output=report.model_dump_json(),
    )


def test_runner_executes_sequentially_once_and_isolates_case_mutation() -> None:
    order: list[str] = []

    def factory(task: AgentTask) -> AgentResult:
        order.append(task.task_id)
        return _debug_success(task)

    target = _AgentTarget("DebugAgent", factory)
    dataset = BenchmarkDataset("suite", [_debug_case("one"), _debug_case("two")])
    before = dataset.list_cases()
    runner = BenchmarkRunner({"DebugAgent": target})

    first = runner.run(dataset)
    second = runner.run(dataset)

    assert order == ["benchmark:one", "benchmark:two"] * 2
    assert len(target.tasks) == 4
    assert target.tasks[0].task_type == "debug"
    assert target.tasks[0].requirement == "synthetic compile marker"
    assert dataset.list_cases() == before
    assert first == second
    assert first.passed_cases == 2


def test_runner_builds_knowledge_query_from_reserved_metadata() -> None:
    target = _KnowledgeTarget()
    case = BenchmarkCase(
        id="knowledge",
        name="Synthetic knowledge",
        category="knowledge",
        input="synthetic query",
        expected={
            "ranked_ids": ["synthetic-doc"],
            "sources": {"synthetic-doc": "LOCAL"},
        },
        metadata={"sources": ["LOCAL"], "top_k": 2, "chip": "ESP32"},
    )

    report = BenchmarkRunner({"KnowledgeGateway": target}).run(
        BenchmarkDataset("knowledge suite", [case])
    )

    assert report.passed_cases == 1
    assert target.queries[0].query == "synthetic query"
    assert target.queries[0].sources == [KnowledgeSource.LOCAL]
    assert target.queries[0].top_k == 2
    assert target.queries[0].metadata == {"chip": "ESP32"}
    assert "PRIVATE KNOWLEDGE BODY" not in report.model_dump_json()


def test_runner_isolates_case_failures_and_redacts_exception_content() -> None:
    class _FailingTarget:
        def run(self, task: AgentTask) -> AgentResult:
            raise RuntimeError("PRIVATE_SENTINEL C:/Users/private/log.txt")

    report = BenchmarkRunner({"DebugAgent": _FailingTarget()}).run(
        BenchmarkDataset("failure", [_debug_case()])
    )

    assert report.failed_cases == 1
    assert report.results[0].score == 0.0
    assert report.results[0].errors == ["benchmark target execution failed"]
    serialized = report.model_dump_json()
    assert "PRIVATE_SENTINEL" not in serialized
    assert "Users" not in serialized


def test_runner_missing_target_fails_case_without_executing_other_targets() -> None:
    report = BenchmarkRunner({}).run(BenchmarkDataset("missing", [_debug_case()]))

    assert report.failed_cases == 1
    assert report.results[0].errors == ["benchmark target is unavailable"]


def test_runner_continues_after_one_case_target_failure() -> None:
    class _SometimesFailingTarget:
        def run(self, task: AgentTask) -> AgentResult:
            if task.task_id == "benchmark:first":
                raise RuntimeError("PRIVATE_SENTINEL")
            return _debug_success(task)

    report = BenchmarkRunner({"DebugAgent": _SometimesFailingTarget()}).run(
        BenchmarkDataset(
            "continue",
            [_debug_case("first"), _debug_case("second")],
        )
    )

    assert [result.case_id for result in report.results] == ["first", "second"]
    assert report.failed_cases == 1
    assert report.passed_cases == 1


def test_runner_rejects_empty_dataset_and_redacts_report_builder_failure() -> None:
    import pytest

    with pytest.raises(BenchmarkRunError, match="dataset is empty"):
        BenchmarkRunner({}).run(BenchmarkDataset("empty"))

    class _FailingBuilder:
        def build(self, *args: object, **kwargs: object) -> object:
            raise RuntimeError("PRIVATE_SENTINEL C:/private/report.txt")

    with pytest.raises(BenchmarkRunError, match="report assembly failed") as captured:
        BenchmarkRunner(
            {"DebugAgent": _AgentTarget("DebugAgent", _debug_success)},
            report_builder=_FailingBuilder(),
        ).run(BenchmarkDataset("report", [_debug_case()]))

    assert "PRIVATE_SENTINEL" not in str(captured.value)


def test_runner_rejects_malformed_or_verbose_report_builder_output() -> None:
    import pytest

    class _MalformedBuilder:
        def build(self, *args: object, **kwargs: object) -> object:
            return None

    class _VerboseBuilder:
        def build(self, *args: object, **kwargs: object) -> object:
            from embedded_copilot.benchmark.exceptions import BenchmarkReportError

            raise BenchmarkReportError("PRIVATE_SENTINEL C:/private/report.txt")

    for builder in (_MalformedBuilder(), _VerboseBuilder()):
        with pytest.raises(BenchmarkRunError, match="report assembly failed") as captured:
            BenchmarkRunner(
                {"DebugAgent": _AgentTarget("DebugAgent", _debug_success)},
                report_builder=builder,
            ).run(BenchmarkDataset("report", [_debug_case()]))
        assert "PRIVATE_SENTINEL" not in str(captured.value)


def test_runner_rebuilds_untrusted_evaluator_result_without_leaking_content() -> None:
    class _VerboseEvaluator:
        def evaluate(self, *args: object, **kwargs: object) -> BenchmarkResult:
            return BenchmarkResult(
                case_id="wrong-case",
                success=False,
                score=0,
                metrics={
                    "recommendation_coverage": 0.0,
                    "finding_coverage": 0.0,
                    "error_type_accuracy": 0.0,
                },
                errors=["PRIVATE_SENTINEL C:/private/debug.log"],
                metadata={
                    "category": "debug",
                    "target_name": "PRIVATE_SENTINEL",
                },
            )

    report = BenchmarkRunner(
        {"DebugAgent": _AgentTarget("DebugAgent", _debug_success)},
        evaluator=_VerboseEvaluator(),
    ).run(BenchmarkDataset("evaluator", [_debug_case()]))

    assert report.failed_cases == 1
    assert report.results[0].case_id == "debug"
    assert report.results[0].errors == ["benchmark evaluation failed"]
    assert "PRIVATE_SENTINEL" not in report.model_dump_json()


def test_runner_sanitizes_custom_evaluator_errors_and_metadata() -> None:
    class _VerboseEvaluator:
        def evaluate(self, *args: object, **kwargs: object) -> BenchmarkResult:
            return BenchmarkResult(
                case_id="debug",
                success=False,
                score=0,
                metrics={
                    "recommendation_coverage": 0.0,
                    "finding_coverage": 0.0,
                    "error_type_accuracy": 0.0,
                },
                errors=["PRIVATE_SENTINEL C:/private/debug.log"],
                metadata={
                    "category": "debug",
                    "target_name": "PRIVATE_SENTINEL",
                },
            )

    report = BenchmarkRunner(
        {"DebugAgent": _AgentTarget("DebugAgent", _debug_success)},
        evaluator=_VerboseEvaluator(),
    ).run(BenchmarkDataset("evaluator", [_debug_case()]))

    assert report.results[0].errors == [
        "metric below required score: error_type_accuracy",
        "metric below required score: finding_coverage",
        "metric below required score: recommendation_coverage",
    ]
    assert report.results[0].metadata == {
        "category": "debug",
        "target_name": "DebugAgent",
    }
    assert "PRIVATE_SENTINEL" not in report.model_dump_json()


def test_runner_isolates_trace_start_failure_and_continues() -> None:
    from embedded_copilot.benchmark.trace import TraceCollector

    class _FailingOnceCollector:
        def __init__(self) -> None:
            self.calls = 0
            self._delegate = TraceCollector(clock=lambda: 1.0)

        def start(self) -> float:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("PRIVATE_SENTINEL C:/private/clock.txt")
            return self._delegate.start()

        def collect(self, **kwargs: object):
            return self._delegate.collect(**kwargs)  # type: ignore[arg-type]

    target = _AgentTarget("DebugAgent", _debug_success)
    report = BenchmarkRunner(
        {"DebugAgent": target},
        trace_collector=_FailingOnceCollector(),
    ).run(
        BenchmarkDataset(
            "trace",
            [_debug_case("first"), _debug_case("second")],
        )
    )

    assert report.failed_cases == 1
    assert report.passed_cases == 1
    assert report.results[0].errors == ["benchmark trace collection failed"]
    assert len(target.tasks) == 1
    assert "PRIVATE_SENTINEL" not in report.model_dump_json()


def test_runner_isolates_trace_collect_failure_and_continues() -> None:
    from embedded_copilot.benchmark.trace import TraceCollector

    class _FailingOnceCollector:
        def __init__(self) -> None:
            self.calls = 0
            self._delegate = TraceCollector(clock=lambda: 1.0)

        def start(self) -> float:
            return self._delegate.start()

        def collect(self, **kwargs: object):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("PRIVATE_SENTINEL C:/private/trace.txt")
            return self._delegate.collect(**kwargs)  # type: ignore[arg-type]

    target = _AgentTarget("DebugAgent", _debug_success)
    report = BenchmarkRunner(
        {"DebugAgent": target},
        trace_collector=_FailingOnceCollector(),
    ).run(
        BenchmarkDataset(
            "trace",
            [_debug_case("first"), _debug_case("second")],
        )
    )

    assert report.failed_cases == 1
    assert report.passed_cases == 1
    assert report.results[0].errors == ["benchmark trace collection failed"]
    assert len(target.tasks) == 2
    assert "PRIVATE_SENTINEL" not in report.model_dump_json()
