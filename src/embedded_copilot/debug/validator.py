from __future__ import annotations

from embedded_copilot.debug.models import DebugReport, DebugValidationResult


_SEVERITIES = {"info", "warning", "error", "critical"}


class DebugValidator:
    """Validate the semantic completeness of an assembled debug report."""

    def validate(self, report: DebugReport) -> DebugValidationResult:
        errors: list[str] = []
        findings = getattr(report, "findings", None) or []
        recommendations = getattr(report, "recommendations", None) or []
        if not _has_text(getattr(report, "summary", None)):
            errors.append("debug report summary must not be empty")
        if not findings:
            errors.append("debug report must contain findings")
        if not any(_has_text(item) for item in recommendations):
            errors.append("debug report must contain recommendations")

        seen: set[str] = set()
        for finding in findings:
            identifier = getattr(finding, "id", "missing")
            key = identifier.casefold() if isinstance(identifier, str) else "missing"
            if key in seen:
                errors.append(f"duplicate debug finding id: {identifier}")
            seen.add(key)
            severity = getattr(finding, "severity", None)
            if not isinstance(severity, str) or severity.casefold() not in _SEVERITIES:
                errors.append(
                    f"unsupported debug finding severity: {severity}"
                )
            if not _has_text(getattr(finding, "description", None)):
                errors.append(
                    f"debug finding description must not be empty: {identifier}"
                )
            finding_evidence = getattr(finding, "evidence", None) or []
            if not any(_has_text(item) for item in finding_evidence):
                errors.append(
                    f"debug finding evidence must not be empty: {identifier}"
                )
            if not _has_text(getattr(finding, "recommendation", None)):
                errors.append(
                    f"debug finding recommendation must not be empty: {identifier}"
                )

        return DebugValidationResult(
            success=not errors,
            errors=errors,
            metadata={
                "finding_count": len(findings),
                "recommendation_count": len(
                    [item for item in recommendations if _has_text(item)]
                ),
            },
        )


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
