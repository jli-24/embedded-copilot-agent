from __future__ import annotations

from embedded_copilot.tool_runtime import BuildStatus
from embedded_copilot.verification_agent.models import (
    FirmwareVerificationSubject,
    VerificationCheckResult,
    VerificationFinding,
    VerificationFindingCategory,
    VerificationSeverity,
    VerificationStatus,
    VerificationSubject,
    VerificationSubjectType,
)


class FirmwareVerificationChecker:
    @property
    def checker_name(self) -> str:
        return "firmware_verification"

    @property
    def supported_subjects(self) -> tuple[VerificationSubjectType, ...]:
        return (VerificationSubjectType.FIRMWARE,)

    def verify(self, subject: VerificationSubject) -> VerificationCheckResult:
        if not isinstance(subject, FirmwareVerificationSubject):
            raise TypeError("firmware verification subject is invalid")
        findings: list[VerificationFinding] = []
        output = subject.build_output
        build_failed = (
            output.build_status is BuildStatus.FAILED or output.error_count > 0
        )
        if build_failed:
            findings.append(
                VerificationFinding(
                    severity=VerificationSeverity.HIGH,
                    category=VerificationFindingCategory.BUILD_STATUS,
                    message="The supplied firmware build did not pass verification.",
                    evidence=(
                        f"observed: build_status={output.build_status.value}",
                        f"observed: error_count={output.error_count}",
                    ),
                    recommendation=(
                        "Review the reported compiler diagnostics before accepting the proposal."
                    ),
                )
            )
        if output.warnings_count > 0:
            findings.append(
                VerificationFinding(
                    severity=VerificationSeverity.MEDIUM,
                    category=VerificationFindingCategory.BUILD_WARNING,
                    message="Compiler warnings require engineer review.",
                    evidence=(f"observed: warnings_count={output.warnings_count}",),
                    recommendation="Review every compiler warning before acceptance.",
                )
            )
        for resource in subject.resources:
            utilization = resource.used_bytes / resource.limit_bytes
            if utilization < 0.8:
                continue
            severity = (
                VerificationSeverity.HIGH
                if utilization >= 0.9
                else VerificationSeverity.MEDIUM
            )
            findings.append(
                VerificationFinding(
                    severity=severity,
                    category=VerificationFindingCategory.RESOURCE_USAGE,
                    message="Firmware resource utilization requires engineer review.",
                    evidence=(
                        f"observed: resource={resource.resource_name}",
                        f"observed: used_bytes={resource.used_bytes}",
                        f"observed: limit_bytes={resource.limit_bytes}",
                    ),
                    recommendation=(
                        "Confirm the resource limit against the target build configuration."
                    ),
                )
            )
        status = (
            VerificationStatus.FAIL
            if build_failed
            else (
                VerificationStatus.REVIEW_REQUIRED
                if findings
                else VerificationStatus.PASS
            )
        )
        return VerificationCheckResult(
            status=status,
            findings=tuple(findings),
            confidence=1.0,
            summary={
                VerificationStatus.PASS: "Firmware verification rules passed.",
                VerificationStatus.FAIL: "The firmware proposal failed verification rules.",
                VerificationStatus.REVIEW_REQUIRED: (
                    "The firmware proposal requires engineer review."
                ),
            }[status],
        )
