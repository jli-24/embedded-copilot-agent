from __future__ import annotations

import copy
from dataclasses import dataclass

from embedded_copilot.integration.report import EngineeringReport


@dataclass(frozen=True, slots=True)
class ReportView:
    summary: dict[str, object]
    sections: dict[str, dict[str, object] | None]
    recommendations: tuple[dict[str, object], ...]
    evidence: tuple[dict[str, object], ...]
    trace: tuple[dict[str, object], ...]


def build_report_view(report: EngineeringReport) -> ReportView:
    validated = EngineeringReport.model_validate(
        copy.deepcopy(report.model_dump(mode="python"))
    )
    sections = {
        "hardware": _section(validated.hardware_section),
        "firmware": _section(validated.firmware_section),
        "pcb": _section(validated.pcb_section),
        "debug": _section(validated.debug_section),
    }
    evidence = tuple(
        finding.model_dump(mode="json")
        for section in (validated.pcb_section, validated.debug_section)
        if section is not None
        for finding in section.findings
    )
    return ReportView(
        summary=validated.summary.model_dump(mode="json"),
        sections=sections,
        recommendations=tuple(
            item.model_dump(mode="json") for item in validated.recommendations
        ),
        evidence=evidence,
        trace=tuple(item.model_dump(mode="json") for item in validated.trace),
    )


def _section(section: object) -> dict[str, object] | None:
    if section is None:
        return None
    model_dump = getattr(section, "model_dump")
    value = model_dump(mode="json")
    return value if isinstance(value, dict) else None
