from __future__ import annotations

from embedded_copilot.pcb.models import PCBReviewReport, PCBValidationResult


_ALLOWED_SEVERITIES = {"info", "warning", "error"}


class PCBValidator:
    """Validate PCB report structure without running DRC or EDA tools."""

    def validate(self, report: PCBReviewReport) -> PCBValidationResult:
        errors: list[str] = []
        if not report.project_name.strip():
            errors.append("PCB project name must not be empty")
        if not report.summary.strip():
            errors.append("PCB review summary must not be empty")
        if not report.issues and not report.passed_rules and not report.warnings:
            errors.append("PCB review report must not be empty")

        issue_ids: set[str] = set()
        for issue in report.issues:
            key = issue.id.casefold()
            if key in issue_ids:
                errors.append(f"duplicate PCB issue id: {issue.id}")
            issue_ids.add(key)
            if issue.severity not in _ALLOWED_SEVERITIES:
                errors.append(f"unsupported PCB issue severity: {issue.severity}")
            if not issue.evidence:
                errors.append(f"PCB issue evidence must not be empty: {issue.id}")
            if not issue.category.strip():
                errors.append(f"PCB issue category must not be empty: {issue.id}")
            if not issue.description.strip():
                errors.append(f"PCB issue description must not be empty: {issue.id}")
            if not issue.recommendation.strip():
                errors.append(f"PCB issue recommendation must not be empty: {issue.id}")

        for label, values in (
            ("passed rule", report.passed_rules),
            ("warning", report.warnings),
        ):
            seen: set[str] = set()
            for value in values:
                if not value.strip():
                    errors.append("PCB report list values must not be empty")
                    continue
                key = value.casefold()
                if key in seen:
                    errors.append(f"duplicate PCB {label}: {value}")
                seen.add(key)

        return PCBValidationResult(
            success=not errors,
            errors=errors,
            metadata={
                "issue_count": len(report.issues),
                "passed_rule_count": len(report.passed_rules),
            },
        )
