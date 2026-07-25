from __future__ import annotations

from embedded_copilot.benchmark.dataset import BenchmarkDataset
from embedded_copilot.benchmark.models import BenchmarkCase
from embedded_copilot.evaluation.renderer import (
    render_evaluation_json,
    render_evaluation_markdown,
)
from embedded_copilot.evaluation.runner import EvaluationRunner
from tests.evaluation.test_runner import RecordingSupervisor, SequenceClock


def test_evaluation_output_never_retains_sensitive_inputs_or_exceptions() -> None:
    canaries = (
        "PRIVATE_REQUEST_CANARY",
        "C:/private/fixture.pdf",
        "SECRET_TOKEN_CANARY",
        "UnifiedPCBModel",
        "UnifiedDatasheetModel",
        "PRIVATE_EXCEPTION_CANARY",
        "AgentResult",
    )
    case = BenchmarkCase(
        id="safe-case-id",
        name="Safe case",
        category="end_to_end",
        input="PRIVATE_REQUEST_CANARY",
        expected={
            "agents": ["FirmwareAgent"],
            "capabilities": ["firmware"],
        },
        metadata={
            "fixture_kind": "synthetic",
            "path": "C:/private/fixture.pdf",
            "token": "SECRET_TOKEN_CANARY",
            "models": ["UnifiedPCBModel", "UnifiedDatasheetModel"],
        },
    )
    report = EvaluationRunner(
        RecordingSupervisor(fail_case="safe-case-id"),
        clock=SequenceClock((0.0, 0.001)),
    ).run(BenchmarkDataset("safe-dataset", [case]))
    output = report.model_dump_json() + render_evaluation_json(
        report
    ) + render_evaluation_markdown(report)

    assert all(canary not in output for canary in canaries)
