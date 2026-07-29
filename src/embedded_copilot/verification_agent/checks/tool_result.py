from __future__ import annotations

from embedded_copilot.tool_runtime import (
    FirmwareBuildOutput,
    FirmwareTestOutput,
    SerialLogOutput,
    ToolMetricUnit,
    ToolResultStatus,
)
from embedded_copilot.verification_agent.models import (
    ToolResultVerificationSubject,
    VerificationCheckResult,
    VerificationFinding,
    VerificationFindingCategory,
    VerificationSeverity,
    VerificationStatus,
    VerificationSubject,
    VerificationSubjectType,
)


class ToolResultChecker:
    @property
    def checker_name(self) -> str:
        return "tool_result"

    @property
    def supported_subjects(self) -> tuple[VerificationSubjectType, ...]:
        return (VerificationSubjectType.TOOL_RESULT,)

    def verify(self, subject: VerificationSubject) -> VerificationCheckResult:
        if not isinstance(subject, ToolResultVerificationSubject):
            raise TypeError("tool result verification subject is invalid")
        result = subject.result
        findings: list[VerificationFinding] = []
        if result.status is not ToolResultStatus.SUCCESS:
            findings.append(
                _finding(
                    VerificationFindingCategory.TOOL_STATUS,
                    f"observed: tool_status={result.status.value}",
                    "The tool result status requires engineer review.",
                )
            )
        expected = _expected_output(result.tool_name)
        if expected is None:
            findings.append(
                _finding(
                    VerificationFindingCategory.TOOL_TRUST,
                    f"observed: tool_name={result.tool_name}",
                    "The tool result is not covered by a trusted verification rule.",
                )
            )
        elif result.status is ToolResultStatus.SUCCESS and result.output is None:
            findings.append(
                _finding(
                    VerificationFindingCategory.TOOL_OUTPUT,
                    "observed: output=missing",
                    "A successful tool result did not include its required output.",
                )
            )
        elif result.output is not None and not isinstance(result.output, expected):
            findings.append(
                _finding(
                    VerificationFindingCategory.TOOL_OUTPUT,
                    f"observed: output_type={type(result.output).__name__}",
                    "The tool output type does not match the declared tool.",
                )
            )
        if (
            result.output is not None
            and getattr(result.output, "execution_mode", None) == "MOCK"
        ):
            findings.append(
                _finding(
                    VerificationFindingCategory.TOOL_TRUST,
                    "observed: execution_mode=MOCK",
                    "Mock output is not production execution evidence.",
                )
            )
        for metric in result.metrics:
            invalid = metric.value < 0 or (
                metric.unit is ToolMetricUnit.PERCENT and metric.value > 100
            )
            if invalid:
                findings.append(
                    _finding(
                        VerificationFindingCategory.TOOL_METRIC,
                        f"observed: invalid_metric={metric.name}",
                        "A tool metric is outside its accepted finite range.",
                    )
                )
        status = (
            VerificationStatus.REVIEW_REQUIRED if findings else VerificationStatus.PASS
        )
        return VerificationCheckResult(
            status=status,
            findings=tuple(findings),
            confidence=1.0,
            summary=(
                "The tool result requires engineer review."
                if findings
                else "Tool result verification rules passed."
            ),
        )


def _finding(
    category: VerificationFindingCategory,
    evidence: str,
    message: str,
) -> VerificationFinding:
    return VerificationFinding(
        severity=VerificationSeverity.MEDIUM,
        category=category,
        message=message,
        evidence=(evidence,),
        recommendation="Obtain complete trusted tool evidence before acceptance.",
    )


def _expected_output(tool_name: str) -> type[object] | None:
    if tool_name == "compile_firmware":
        return FirmwareBuildOutput
    if tool_name == "read_serial_log":
        return SerialLogOutput
    if tool_name == "run_firmware_test":
        return FirmwareTestOutput
    return None
