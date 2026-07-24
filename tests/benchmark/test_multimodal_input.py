from __future__ import annotations

from collections.abc import Mapping

from embedded_copilot.benchmark.datasets.synthetic import (
    create_synthetic_foundation_dataset,
    create_synthetic_multimodal_input_dataset,
)
from embedded_copilot.benchmark.runner import BenchmarkRunner
from embedded_copilot.input.models import AttachmentType, UnifiedInputContext
from embedded_copilot.supervisor.agent import SupervisorAgent
from embedded_copilot.supervisor.analyzer import SupervisorRequirementAnalyzer
from embedded_copilot.supervisor.models import SupervisorTask


class _RecordingAnalyzer(SupervisorRequirementAnalyzer):
    def __init__(self) -> None:
        self.contexts: list[UnifiedInputContext | None] = []

    def analyze(
        self,
        request: str,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> SupervisorTask:
        result = super().analyze(request, metadata=metadata)
        self.contexts.append(result.input_context)
        return result


def test_synthetic_multimodal_dataset_is_separate_and_preserves_golden_cases() -> None:
    dataset = create_synthetic_multimodal_input_dataset()
    cases = dataset.list_cases()

    assert dataset.name == "synthetic-multimodal-input"
    assert [case.id for case in cases] == [
        "synthetic-input-text",
        "synthetic-input-image",
        "synthetic-input-eda",
        "synthetic-input-log",
    ]
    assert all(case.category == "routing" for case in cases)
    assert all(case.metadata["fixture_kind"] == "synthetic" for case in cases)
    assert len(create_synthetic_foundation_dataset().list_cases()) == 7


def test_benchmark_routes_four_typed_contexts_through_supervisor_adapter() -> None:
    analyzer = _RecordingAnalyzer()
    supervisor = SupervisorAgent(analyzer=analyzer)

    report = BenchmarkRunner({"SupervisorAgent": supervisor}).run(
        create_synthetic_multimodal_input_dataset()
    )

    assert report.passed_cases == 4
    assert report.failed_cases == 0
    assert len(analyzer.contexts) == 4
    assert all(isinstance(context, UnifiedInputContext) for context in analyzer.contexts)
    assert [
        context.attachments[0].media_type if context and context.attachments else None
        for context in analyzer.contexts
    ] == [None, AttachmentType.IMAGE, AttachmentType.EDA, AttachmentType.LOG]
    assert "_benchmark_input_context" not in report.model_dump_json()


def test_benchmark_rejects_malformed_context_without_content_leak() -> None:
    dataset = create_synthetic_multimodal_input_dataset()
    case = dataset.get_case("synthetic-input-image")
    payload = case.model_dump(mode="python")
    payload["metadata"]["_benchmark_input_context"] = {
        "text": "PRIVATE_SENTINEL",
        "attachments": [{"filename": "C:/Users/private/image.png"}],
    }
    from embedded_copilot.benchmark.dataset import BenchmarkDataset
    from embedded_copilot.benchmark.models import BenchmarkCase

    report = BenchmarkRunner({"SupervisorAgent": SupervisorAgent()}).run(
        BenchmarkDataset("invalid-input", [BenchmarkCase.model_validate(payload)])
    )

    assert report.failed_cases == 1
    assert report.results[0].errors == ["benchmark target execution failed"]
    assert "PRIVATE_SENTINEL" not in report.model_dump_json()
    assert "Users" not in report.model_dump_json()
