from __future__ import annotations

from embedded_copilot.firmware.review.models import FirmwareFinding


_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def finding_sort_key(finding: FirmwareFinding) -> tuple[int, str, int, str]:
    return (
        _SEVERITY_ORDER[finding.severity],
        finding.filename.casefold(),
        finding.line,
        finding.rule_id,
    )


def finding(
    *,
    rule_id: str,
    severity: str,
    description: str,
    recommendation: str,
    source_id: str,
    filename: str,
    line: int,
) -> FirmwareFinding:
    return FirmwareFinding(
        rule_id=rule_id,
        severity=severity,  # type: ignore[arg-type]
        description=description,
        recommendation=recommendation,
        source_ids=(f"{source_id}#line:{line}",),
        filename=filename,
        line=line,
    )
