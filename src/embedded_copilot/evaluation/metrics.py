from __future__ import annotations

from collections.abc import Iterable

from embedded_copilot.integration.report import EngineeringReport


_PLAN_PREFIX = "supervisor:plan:"
_SECTION_BY_AGENT = {
    "firmwareagent": "firmware_section",
    "hardwareagent": "hardware_section",
    "pcbagent": "pcb_section",
    "debugagent": "debug_section",
}


def _normalized(values: Iterable[str]) -> set[str]:
    return {value.strip().casefold() for value in values if value.strip()}


def _planned_agents(report: EngineeringReport) -> set[str]:
    planned: set[str] = set()
    for event in report.trace:
        if event.stage != "agent_planned" or not event.source_id.startswith(_PLAN_PREFIX):
            continue
        name = event.source_id.removeprefix(_PLAN_PREFIX).strip()
        if name:
            planned.add(name.casefold())
    return planned


def routing_accuracy(
    report: EngineeringReport,
    expected_agents: tuple[str, ...],
) -> float:
    expected = _normalized(expected_agents)
    planned = _planned_agents(report)
    union = expected | planned
    return len(expected & planned) / len(union) if union else 0.0


def agent_success_rate(report: EngineeringReport) -> float:
    planned = _planned_agents(report)
    if not planned:
        return 0.0
    succeeded = {
        event.source_agent.casefold()
        for event in report.trace
        if event.stage == "agent_executed" and event.status == "success"
    }
    return len(planned & succeeded) / len(planned)


def report_completeness(
    report: EngineeringReport,
    expected_agents: tuple[str, ...],
) -> float:
    expected = _normalized(expected_agents)
    expected_sections = {
        _SECTION_BY_AGENT[name]
        for name in expected
        if name in _SECTION_BY_AGENT
    }
    if not expected_sections or len(expected_sections) != len(expected):
        return 0.0
    present = sum(getattr(report, name) is not None for name in expected_sections)
    return present / len(expected_sections)


def evidence_traceability(report: EngineeringReport) -> float:
    values: list[object] = [report.summary]
    sections = tuple(
        section
        for section in (
            report.hardware_section,
            report.firmware_section,
            report.pcb_section,
            report.debug_section,
        )
        if section is not None
    )
    values.extend(sections)
    values.extend(report.recommendations)
    for section in (report.pcb_section, report.debug_section):
        if section is not None:
            values.extend(section.findings)
    if report.debug_section is not None:
        values.extend(report.debug_section.recommendations)
    return float(
        all(
            isinstance(getattr(value, "source_agent", None), str)
            and bool(getattr(value, "source_agent", "").strip())
            and isinstance(getattr(value, "source_id", None), str)
            and bool(getattr(value, "source_id", "").strip())
            for value in values
        )
    )
