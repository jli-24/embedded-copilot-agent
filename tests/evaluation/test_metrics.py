from __future__ import annotations

from embedded_copilot.evaluation.metrics import (
    agent_success_rate,
    evidence_traceability,
    report_completeness,
    routing_accuracy,
)
from embedded_copilot.integration.report import EngineeringReport, ReportSummary
from tests.evaluation.factories import engineering_report


def test_routing_accuracy_uses_case_insensitive_intersection_over_union() -> None:
    report = engineering_report()

    assert routing_accuracy(
        report,
        ("firmwareagent", "PCBAgent"),
    ) == 1 / 3
    assert routing_accuracy(report, ()) == 0.0


def test_routing_accuracy_is_zero_when_planning_trace_is_missing() -> None:
    report = engineering_report(
        planned=(),
        successful=(),
        include_firmware=False,
        include_hardware=False,
    )

    assert routing_accuracy(report, ("FirmwareAgent",)) == 0.0


def test_agent_success_rate_uses_planned_agents_as_denominator() -> None:
    report = engineering_report(successful=("FirmwareAgent",))

    assert agent_success_rate(report) == 0.5
    assert agent_success_rate(
        engineering_report(
            planned=(),
            successful=(),
            include_firmware=False,
            include_hardware=False,
        )
    ) == 0.0


def test_report_completeness_checks_only_expected_domain_sections() -> None:
    report = engineering_report(include_hardware=False)

    assert report_completeness(
        report,
        ("FirmwareAgent", "HardwareAgent"),
    ) == 0.5
    assert report_completeness(report, ()) == 0.0


def test_evidence_traceability_accepts_complete_valid_provenance() -> None:
    assert evidence_traceability(engineering_report()) == 1.0


def test_evidence_traceability_rejects_missing_source_identifier() -> None:
    invalid_summary = ReportSummary.model_construct(
        text="Synthetic evaluation completed.",
        succeeded=0,
        failed=0,
        source_agent="SupervisorAgent",
        source_id="",
    )
    invalid_report = EngineeringReport.model_construct(
        summary=invalid_summary,
        hardware_section=None,
        firmware_section=None,
        pcb_section=None,
        debug_section=None,
        recommendations=(),
        trace=(),
    )

    assert evidence_traceability(invalid_report) == 0.0
