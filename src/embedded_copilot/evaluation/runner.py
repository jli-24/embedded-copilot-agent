from __future__ import annotations

import copy
import time
from collections.abc import Callable, Mapping

from embedded_copilot import __version__
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.benchmark.dataset import BenchmarkDataset
from embedded_copilot.benchmark.models import BenchmarkCase
from embedded_copilot.evaluation.metrics import (
    agent_success_rate,
    evidence_traceability,
    report_completeness,
    routing_accuracy,
)
from embedded_copilot.evaluation.models import (
    EvaluationCaseResult,
    EvaluationFailureCode,
    EvaluationReport,
)
from embedded_copilot.evaluation.report import build_evaluation_report
from embedded_copilot.evaluation.scenarios import expected_agents
from embedded_copilot.input.adapters.supervisor import attach_input_context
from embedded_copilot.input.models import UnifiedInputContext
from embedded_copilot.integration.report import EngineeringReport


_BENCHMARK_INPUT_CONTEXT_KEY = "_benchmark_input_context"


class EvaluationRunError(RuntimeError):
    pass


class EvaluationRunner:
    def __init__(
        self,
        supervisor: object,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if not callable(getattr(supervisor, "run", None)):
            raise ValueError("evaluation supervisor is invalid")
        if clock is not None and not callable(clock):
            raise ValueError("evaluation clock is invalid")
        self._supervisor = supervisor
        self._clock = clock if clock is not None else time.perf_counter

    def run(self, dataset: BenchmarkDataset) -> EvaluationReport:
        if not isinstance(dataset, BenchmarkDataset):
            raise EvaluationRunError("evaluation dataset is invalid")
        cases = dataset.list_cases()
        if not cases:
            raise EvaluationRunError("evaluation dataset is empty")
        try:
            expectations = {
                case.id: expected_agents(case)
                for case in cases
            }
        except Exception:
            raise EvaluationRunError("evaluation scenario is invalid") from None
        results = tuple(
            self._run_case(case, expectations[case.id]) for case in cases
        )
        try:
            return build_evaluation_report(
                version=__version__,
                dataset=dataset.name,
                cases=results,
            )
        except Exception:
            raise EvaluationRunError("evaluation report assembly failed") from None

    def _run_case(
        self,
        case: BenchmarkCase,
        expected: tuple[str, ...],
    ) -> EvaluationCaseResult:
        try:
            started_at = self._clock()
        except Exception:
            return self._failure(case.id, 0.0, "evaluation_failed")
        try:
            task = self._task(case)
            result = self._supervisor.run(task)
        except Exception:
            return self._failure(
                case.id,
                self._elapsed(started_at),
                "supervisor_execution_failed",
            )
        elapsed_ms = self._elapsed(started_at)
        if not isinstance(result, AgentResult) or result.status is not AgentStatus.SUCCESS:
            return self._failure(
                case.id,
                elapsed_ms,
                "supervisor_execution_failed",
            )
        metadata = copy.deepcopy(result.metadata)
        if not isinstance(metadata, Mapping) or "engineering_report" not in metadata:
            return self._failure(
                case.id,
                elapsed_ms,
                "engineering_report_missing",
            )
        try:
            report = EngineeringReport.model_validate(metadata["engineering_report"])
        except Exception:
            return self._failure(
                case.id,
                elapsed_ms,
                "engineering_report_invalid",
            )
        try:
            routing = routing_accuracy(report, expected)
            success_rate = agent_success_rate(report)
            completeness = report_completeness(report, expected)
            traceability = evidence_traceability(report)
            quality = (routing, success_rate, completeness, traceability)
            succeeded = all(value == 1.0 for value in quality)
            return EvaluationCaseResult(
                case_id=case.id,
                success=succeeded,
                routing_accuracy=routing,
                agent_success_rate=success_rate,
                report_completeness=completeness,
                evidence_traceability=traceability,
                execution_latency_ms=elapsed_ms,
                failure_code=None if succeeded else "evaluation_failed",
            )
        except Exception:
            return self._failure(
                case.id,
                elapsed_ms,
                "evaluation_failed",
            )

    def _task(self, case: BenchmarkCase) -> AgentTask:
        metadata = copy.deepcopy(case.metadata)
        raw_context = metadata.pop(_BENCHMARK_INPUT_CONTEXT_KEY, None)
        context = UnifiedInputContext.model_validate(
            copy.deepcopy(raw_context) if raw_context is not None else {}
        )
        task = AgentTask(
            task_id=f"evaluation:{case.id}",
            task_type=case.category,
            requirement=case.input,
            metadata=metadata,
        )
        return attach_input_context(task, context)

    def _elapsed(self, started_at: float) -> float:
        try:
            return round(max(0.0, (self._clock() - started_at) * 1000), 6)
        except Exception:
            return 0.0

    @staticmethod
    def _failure(
        case_id: str,
        latency_ms: float,
        code: EvaluationFailureCode,
    ) -> EvaluationCaseResult:
        return EvaluationCaseResult(
            case_id=case_id,
            success=False,
            routing_accuracy=0.0,
            agent_success_rate=0.0,
            report_completeness=0.0,
            evidence_traceability=0.0,
            execution_latency_ms=latency_ms,
            failure_code=code,
        )
