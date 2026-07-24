from __future__ import annotations

import copy
from collections.abc import Mapping

from embedded_copilot.benchmark.dataset import BenchmarkDataset
from embedded_copilot.benchmark.exceptions import BenchmarkRunError
from embedded_copilot.benchmark.metrics import ScoreAggregator
from embedded_copilot.benchmark.models import (
    BenchmarkCase,
    BenchmarkReport,
    BenchmarkResult,
)


_TARGET_NAMES = {
    "routing": "SupervisorAgent",
    "firmware": "FirmwareAgent",
    "hardware": "HardwareAgent",
    "pcb": "PCBAgent",
    "debug": "DebugAgent",
    "knowledge": "KnowledgeGateway",
    "end_to_end": "SupervisorAgent",
}

_EXPECTED_METRICS = {
    "routing": ("agent_selection_accuracy", "capability_coverage"),
    "firmware": (
        "platform_accuracy",
        "component_coverage",
        "template_coverage",
    ),
    "hardware": (
        "component_keyword_accuracy",
        "interface_accuracy",
        "constraint_coverage",
    ),
    "pcb": ("rule_coverage", "issue_coverage", "severity_accuracy"),
    "debug": (
        "error_type_accuracy",
        "finding_coverage",
        "recommendation_coverage",
    ),
    "knowledge": (
        "retrieval_hit_rate",
        "source_accuracy",
        "ranking_accuracy",
        "recall_at_k",
        "mrr",
    ),
    "end_to_end": (
        "agent_selection_accuracy",
        "capability_coverage",
        "pipeline_completion",
        "handoff_success",
    ),
}
_BENCHMARK_INPUT_CONTEXT_KEY = "_benchmark_input_context"


class BenchmarkRunner:
    def __init__(
        self,
        targets: Mapping[str, object],
        evaluator: object | None = None,
        trace_collector: object | None = None,
        report_builder: object | None = None,
    ) -> None:
        from embedded_copilot.benchmark.evaluator import BenchmarkEvaluator
        from embedded_copilot.benchmark.report import BenchmarkReportBuilder
        from embedded_copilot.benchmark.trace import TraceCollector

        if not isinstance(targets, Mapping):
            raise ValueError("benchmark targets must be a mapping")
        self._targets = dict(targets)
        self._evaluator = evaluator if evaluator is not None else BenchmarkEvaluator()
        self._trace_collector = (
            trace_collector if trace_collector is not None else TraceCollector()
        )
        self._report_builder = (
            report_builder if report_builder is not None else BenchmarkReportBuilder()
        )

    def run(self, dataset: BenchmarkDataset):
        if not isinstance(dataset, BenchmarkDataset):
            raise BenchmarkRunError("benchmark dataset is invalid")
        cases = dataset.list_cases()
        if not cases:
            raise BenchmarkRunError("benchmark dataset is empty")
        results = [self._run_case(case) for case in cases]
        try:
            report = self._report_builder.build(
                dataset.name,
                results,
                trace_enabled=self._trace_collector is not None,
            )
            if not isinstance(report, BenchmarkReport):
                raise TypeError("invalid benchmark report")
            return BenchmarkReport.model_validate(report.model_dump(mode="python"))
        except Exception:
            raise BenchmarkRunError("benchmark report assembly failed") from None

    def _run_case(self, case: BenchmarkCase) -> BenchmarkResult:
        target_name = _TARGET_NAMES[case.category]
        target = self._targets.get(target_name)
        if target is None:
            return self._failure(case, target_name, "benchmark target is unavailable")
        try:
            started_at = self._trace_collector.start()
        except Exception:
            return self._failure(
                case,
                target_name,
                "benchmark trace collection failed",
            )
        try:
            raw_result = self._invoke(target, case)
        except Exception:
            try:
                self._trace_collector.collect(
                    case_id=case.id,
                    target_name=target_name,
                    result=None,
                    started_at=started_at,
                    execution_succeeded=False,
                )
            except Exception:
                pass
            return self._failure(
                case,
                target_name,
                "benchmark target execution failed",
            )
        try:
            trace = self._trace_collector.collect(
                case_id=case.id,
                target_name=target_name,
                result=raw_result,
                started_at=started_at,
                execution_succeeded=True,
            )
        except Exception:
            return self._failure(
                case,
                target_name,
                "benchmark trace collection failed",
            )
        try:
            evaluated = self._evaluator.evaluate(
                case.model_copy(deep=True),
                raw_result,
                trace=trace,
            )
            return self._normalize_evaluation(case, target_name, evaluated)
        except Exception:
            return self._failure(case, target_name, "benchmark evaluation failed")

    @staticmethod
    def _normalize_evaluation(
        case: BenchmarkCase,
        target_name: str,
        evaluated: object,
    ) -> BenchmarkResult:
        if not isinstance(evaluated, BenchmarkResult):
            raise TypeError("invalid benchmark evaluation")
        validated = BenchmarkResult.model_validate(
            evaluated.model_dump(mode="python")
        )
        if validated.case_id.casefold() != case.id.casefold():
            raise ValueError("benchmark evaluation case id does not match")
        metric_names = _EXPECTED_METRICS[case.category]
        if set(validated.metrics) != set(metric_names):
            raise ValueError("benchmark evaluation metrics are invalid")
        metrics = {name: validated.metrics[name] for name in metric_names}
        score = ScoreAggregator.aggregate(list(metrics.values()))
        errors = [
            f"metric below required score: {name}"
            for name, value in metrics.items()
            if value != 1.0
        ]
        return BenchmarkResult(
            case_id=case.id,
            success=not errors,
            score=score,
            metrics=metrics,
            errors=errors,
            metadata={"category": case.category, "target_name": target_name},
        )

    @staticmethod
    def _invoke(target: object, case: BenchmarkCase) -> object:
        if case.category == "knowledge":
            from embedded_copilot.knowledge.models import KnowledgeQuery

            metadata = copy.deepcopy(case.metadata)
            sources = metadata.pop("sources", [])
            top_k = metadata.pop("top_k", 4)
            query = KnowledgeQuery(
                query=case.input,
                sources=sources,
                top_k=top_k,
                metadata=metadata,
            )
            search = getattr(target, "search", None)
            if not callable(search):
                raise TypeError("knowledge target must implement search")
            return search(query)
        from embedded_copilot.agents.types import AgentTask

        metadata = copy.deepcopy(case.metadata)
        raw_input_context = metadata.pop(_BENCHMARK_INPUT_CONTEXT_KEY, None)
        task = AgentTask(
            task_id=f"benchmark:{case.id}",
            task_type=case.category,
            requirement=case.input,
            metadata=metadata,
        )
        if raw_input_context is not None:
            if case.category not in {"routing", "end_to_end"}:
                raise TypeError("input context requires a supervisor target")
            from embedded_copilot.input.adapters.supervisor import (
                attach_input_context,
            )
            from embedded_copilot.input.models import UnifiedInputContext

            context = UnifiedInputContext.model_validate(raw_input_context)
            task = attach_input_context(task, context)
        run = getattr(target, "run", None)
        if not callable(run):
            raise TypeError("agent target must implement run")
        return run(task)

    @staticmethod
    def _failure(
        case: BenchmarkCase,
        target_name: str,
        error: str,
    ) -> BenchmarkResult:
        return BenchmarkResult(
            case_id=case.id,
            success=False,
            score=0,
            errors=[error],
            metadata={"category": case.category, "target_name": target_name},
        )
