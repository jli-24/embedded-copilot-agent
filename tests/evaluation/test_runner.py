from __future__ import annotations

from collections.abc import Iterable

import pytest

from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.benchmark.dataset import BenchmarkDataset
from embedded_copilot.benchmark.models import BenchmarkCase
from embedded_copilot.evaluation.runner import EvaluationRunError, EvaluationRunner
from embedded_copilot.evaluation.scenarios import create_default_evaluation_dataset
from embedded_copilot.input.adapters.supervisor import _consume_input_context
from tests.evaluation.factories import engineering_report


_EXPECTED: dict[str, tuple[str, ...]] = {
    "synthetic-esp32-camera-integration": (
        "FirmwareAgent",
        "HardwareAgent",
        "PCBAgent",
    ),
    "synthetic-firmware-debug-integration": (
        "FirmwareAgent",
        "DebugAgent",
    ),
    "synthetic-pcb-review-integration": (
        "HardwareAgent",
        "PCBAgent",
    ),
}


class SequenceClock:
    def __init__(self, values: Iterable[float]) -> None:
        self._values = iter(values)

    def __call__(self) -> float:
        return next(self._values)


class RecordingSupervisor:
    def __init__(self, *, fail_case: str | None = None) -> None:
        self.tasks: list[AgentTask] = []
        self._fail_case = fail_case

    def run(self, task: AgentTask) -> AgentResult:
        self.tasks.append(task.model_copy(deep=True))
        case_id = task.task_id.removeprefix("evaluation:")
        if case_id == self._fail_case:
            raise RuntimeError("PRIVATE_EXCEPTION_CANARY C:/private/source.pdf")
        expected = _EXPECTED[case_id]
        report = engineering_report(
            planned=expected,
            successful=expected,
            include_firmware="FirmwareAgent" in expected,
            include_hardware="HardwareAgent" in expected,
            include_pcb="PCBAgent" in expected,
            include_debug="DebugAgent" in expected,
        )
        return AgentResult(
            agent_name="SupervisorAgent",
            status=AgentStatus.SUCCESS,
            output="synthetic supervisor result",
            metadata={"engineering_report": report.model_dump(mode="json")},
        )


def test_runner_executes_cases_once_in_order_through_supervisor_adapter() -> None:
    supervisor = RecordingSupervisor()
    report = EvaluationRunner(
        supervisor,
        clock=SequenceClock((0.0, 0.001, 1.0, 1.002, 2.0, 2.003)),
    ).run(create_default_evaluation_dataset())

    assert [task.task_id for task in supervisor.tasks] == [
        f"evaluation:{case_id}" for case_id in _EXPECTED
    ]
    assert [case.execution_latency_ms for case in report.cases] == [1.0, 2.0, 3.0]
    assert all(case.success for case in report.cases)
    for task in supervisor.tasks:
        metadata, context = _consume_input_context(task.metadata)
        assert context is not None
        assert "_benchmark_input_context" not in metadata
        assert all(attachment.size_bytes == 256 for attachment in context.attachments)


def test_runner_isolates_safe_case_failure_and_continues() -> None:
    first_case = next(iter(_EXPECTED))
    report = EvaluationRunner(
        RecordingSupervisor(fail_case=first_case),
        clock=SequenceClock((0.0, 0.001, 1.0, 1.002, 2.0, 2.003)),
    ).run(create_default_evaluation_dataset())

    assert [case.success for case in report.cases] == [False, True, True]
    assert report.failures[0].case_id == first_case
    assert report.failures[0].code == "supervisor_execution_failed"
    assert report.summary.total == 3
    assert report.summary.passed == 2


def test_runner_rejects_empty_or_non_end_to_end_dataset() -> None:
    runner = EvaluationRunner(RecordingSupervisor(), clock=lambda: 0.0)
    with pytest.raises(EvaluationRunError, match="evaluation dataset is empty"):
        runner.run(BenchmarkDataset("empty", []))
    invalid = BenchmarkDataset(
        "invalid",
        [
            BenchmarkCase(
                id="routing-case",
                name="Routing case",
                category="routing",
                input="Synthetic routing input.",
                expected={"agents": ["FirmwareAgent"], "capabilities": ["firmware"]},
                metadata={"fixture_kind": "synthetic"},
            )
        ],
    )
    with pytest.raises(EvaluationRunError, match="evaluation scenario is invalid"):
        runner.run(invalid)


class InvalidReportSupervisor:
    def __init__(self, result: AgentResult) -> None:
        self._result = result

    def run(self, task: AgentTask) -> AgentResult:
        return self._result.model_copy(deep=True)


@pytest.mark.parametrize(
    ("result", "expected_code"),
    [
        (
            AgentResult(
                agent_name="SupervisorAgent",
                status=AgentStatus.ERROR,
                output="safe failure",
            ),
            "supervisor_execution_failed",
        ),
        (
            AgentResult(
                agent_name="SupervisorAgent",
                status=AgentStatus.SUCCESS,
                output="safe result",
            ),
            "engineering_report_missing",
        ),
        (
            AgentResult(
                agent_name="SupervisorAgent",
                status=AgentStatus.SUCCESS,
                output="safe result",
                metadata={"engineering_report": {"invalid": True}},
            ),
            "engineering_report_invalid",
        ),
    ],
)
def test_runner_maps_invalid_supervisor_results_to_safe_codes(
    result: AgentResult,
    expected_code: str,
) -> None:
    case = create_default_evaluation_dataset().list_cases()[0]
    report = EvaluationRunner(
        InvalidReportSupervisor(result),
        clock=SequenceClock((0.0, 0.001)),
    ).run(BenchmarkDataset("single-case", [case]))

    assert report.cases[0].failure_code == expected_code


def test_runner_maps_clock_failure_to_safe_evaluation_failure() -> None:
    case = create_default_evaluation_dataset().list_cases()[0]

    def failing_clock() -> float:
        raise RuntimeError("PRIVATE_CLOCK_CANARY C:/private/timing.log")

    report = EvaluationRunner(
        RecordingSupervisor(),
        clock=failing_clock,
    ).run(BenchmarkDataset("single-case", [case]))

    assert report.cases[0].failure_code == "evaluation_failed"
    assert report.cases[0].execution_latency_ms == 0.0
    assert "PRIVATE_CLOCK_CANARY" not in report.model_dump_json()
