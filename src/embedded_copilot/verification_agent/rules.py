from __future__ import annotations

from embedded_copilot.verification_agent.models import (
    VerificationCheckResult,
    VerificationFinding,
    VerificationResult,
    VerificationStatus,
)


def aggregate_results(
    request_id: str,
    results: tuple[VerificationCheckResult, ...],
) -> VerificationResult:
    status = max((item.status for item in results), key=_status_rank)
    findings = tuple(
        sorted(
            (finding for item in results for finding in item.findings),
            key=_finding_key,
        )
    )
    confidence = min(item.confidence for item in results)
    summary = {
        VerificationStatus.PASS: "The supplied proposal passed the configured verification rules.",
        VerificationStatus.REVIEW_REQUIRED: (
            "The supplied proposal requires engineer review before acceptance."
        ),
        VerificationStatus.FAIL: (
            "The supplied proposal failed verification rules; findings remain "
            "unverified candidates, not confirmed hardware faults."
        ),
    }[status]
    return VerificationResult(
        request_id=request_id,
        status=status,
        findings=findings,
        confidence=confidence,
        summary=summary,
    )


def _finding_key(finding: VerificationFinding) -> tuple[object, ...]:
    return (
        finding.category.value,
        finding.severity.value,
        finding.message,
        finding.evidence,
        finding.recommendation,
    )


def _status_rank(status: VerificationStatus) -> int:
    if status is VerificationStatus.FAIL:
        return 2
    if status is VerificationStatus.REVIEW_REQUIRED:
        return 1
    return 0
