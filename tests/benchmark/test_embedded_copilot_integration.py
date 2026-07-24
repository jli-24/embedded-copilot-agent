from __future__ import annotations

import copy

from embedded_copilot.agents.types import AgentStatus, AgentTask

from embedded_copilot.benchmark.datasets.synthetic import (
    create_synthetic_embedded_copilot_integration_dataset,
    create_synthetic_foundation_dataset,
)
from embedded_copilot.benchmark.runner import BenchmarkRunner
from embedded_copilot.input.adapters.supervisor import attach_input_context
from embedded_copilot.input.models import UnifiedInputContext
from embedded_copilot.integration.report import EngineeringReport
from embedded_copilot.supervisor.agent import SupervisorAgent


def test_embedded_copilot_dataset_adds_three_isolated_end_to_end_cases() -> None:
    dataset = create_synthetic_embedded_copilot_integration_dataset()
    cases = dataset.list_cases()

    assert dataset.name == "synthetic-embedded-copilot-integration"
    assert [case.id for case in cases] == [
        "synthetic-esp32-camera-integration",
        "synthetic-firmware-debug-integration",
        "synthetic-pcb-review-integration",
    ]
    assert all(case.category == "end_to_end" for case in cases)
    assert all(case.metadata["fixture_kind"] == "synthetic" for case in cases)
    assert len(create_synthetic_foundation_dataset().list_cases()) == 7


def test_embedded_copilot_dataset_passes_existing_public_metrics() -> None:
    report = BenchmarkRunner(
        {"SupervisorAgent": SupervisorAgent()}
    ).run(create_synthetic_embedded_copilot_integration_dataset())

    assert report.total_cases == 3
    assert report.passed_cases == 3
    assert report.failed_cases == 0


def test_each_embedded_copilot_case_produces_traceable_engineering_report() -> None:
    expected_sections = {
        "synthetic-esp32-camera-integration": {
            "firmware_section",
            "hardware_section",
            "pcb_section",
        },
        "synthetic-firmware-debug-integration": {
            "firmware_section",
            "debug_section",
        },
        "synthetic-pcb-review-integration": {
            "hardware_section",
            "pcb_section",
        },
    }

    for case in create_synthetic_embedded_copilot_integration_dataset().list_cases():
        metadata = copy.deepcopy(case.metadata)
        raw_context = metadata.pop("_benchmark_input_context")
        task = attach_input_context(
            AgentTask(
                task_id=f"report:{case.id}",
                task_type=case.category,
                requirement=case.input,
                metadata=metadata,
            ),
            UnifiedInputContext.model_validate(raw_context),
        )
        result = SupervisorAgent().run(task)
        report = EngineeringReport.model_validate(
            result.metadata["engineering_report"]
        )
        present_sections = {
            name
            for name in (
                "firmware_section",
                "hardware_section",
                "pcb_section",
                "debug_section",
            )
            if getattr(report, name) is not None
        }
        execution_sources = {
            event.source_id
            for event in report.trace
            if event.stage == "agent_executed"
        }

        assert result.status is AgentStatus.SUCCESS
        assert present_sections == expected_sections[case.id]
        assert {
            getattr(report, name).source_id for name in present_sections
        } <= execution_sources
        assert report.summary.source_id == report.trace[-1].source_id
        serialized = report.model_dump_json()
        assert "UnifiedPCBModel" not in serialized
        assert "UnifiedDatasheetModel" not in serialized
        assert ".kicad_pcb" not in serialized
        assert ".pdf" not in serialized
