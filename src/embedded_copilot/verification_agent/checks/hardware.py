from __future__ import annotations

from collections import defaultdict

from embedded_copilot.verification_agent.models import (
    HardwareVerificationSubject,
    VerificationCheckResult,
    VerificationFinding,
    VerificationFindingCategory,
    VerificationSeverity,
    VerificationStatus,
    VerificationSubject,
    VerificationSubjectType,
)


class HardwareConstraintChecker:
    @property
    def checker_name(self) -> str:
        return "hardware_constraint"

    @property
    def supported_subjects(self) -> tuple[VerificationSubjectType, ...]:
        return (VerificationSubjectType.HARDWARE,)

    def verify(self, subject: VerificationSubject) -> VerificationCheckResult:
        if not isinstance(subject, HardwareVerificationSubject):
            raise TypeError("hardware verification subject is invalid")
        findings = [
            *_pin_findings(subject),
            *_interface_findings(subject),
            *_power_findings(subject),
        ]
        has_evidence = bool(
            subject.fusion_request.pin_candidates
            or subject.interface_bindings
            or subject.power_connections
        )
        if not has_evidence:
            findings.append(
                VerificationFinding(
                    severity=VerificationSeverity.MEDIUM,
                    category=VerificationFindingCategory.INSUFFICIENT_EVIDENCE,
                    message="No checkable hardware relationships were supplied.",
                    evidence=("observed: hardware_relationship_count=0",),
                    recommendation=(
                        "Provide simultaneous pin, interface, or power candidates for review."
                    ),
                )
            )
            return VerificationCheckResult(
                status=VerificationStatus.REVIEW_REQUIRED,
                findings=tuple(findings),
                confidence=0.5,
                summary="Hardware evidence is insufficient for verification.",
            )
        status = VerificationStatus.FAIL if findings else VerificationStatus.PASS
        return VerificationCheckResult(
            status=status,
            findings=tuple(findings),
            confidence=1.0,
            summary=(
                "The hardware proposal failed verification rules."
                if findings
                else "Hardware verification rules passed."
            ),
        )


def _pin_findings(
    subject: HardwareVerificationSubject,
) -> tuple[VerificationFinding, ...]:
    by_pin: dict[str, set[str]] = defaultdict(set)
    for candidate in subject.fusion_request.pin_candidates:
        by_pin[candidate.pin].add(candidate.function)
    findings: list[VerificationFinding] = []
    for pin, items in sorted(by_pin.items()):
        if len(items) <= 1:
            continue
        sample = tuple(sorted(items))[:4]
        findings.append(
            VerificationFinding(
                severity=VerificationSeverity.HIGH,
                category=VerificationFindingCategory.PIN_CONFLICT,
                message=(
                    "The proposal assigns incompatible candidate functions to one pin."
                ),
                evidence=(
                    f"observed: pin={pin}",
                    f"observed: candidate_count={len(items)}",
                    "observed: candidate_sample=" + ",".join(sample),
                ),
                recommendation=(
                    "Confirm which candidate functions are simultaneously enabled and revise the proposal."
                ),
            )
        )
    return tuple(findings)


def _interface_findings(
    subject: HardwareVerificationSubject,
) -> tuple[VerificationFinding, ...]:
    by_signal: dict[tuple[str, str], set[str]] = defaultdict(set)
    for binding in subject.interface_bindings:
        by_signal[(binding.interface_id, binding.signal)].add(binding.pin)
    findings: list[VerificationFinding] = []
    for (interface_id, signal), pins in sorted(by_signal.items()):
        if len(pins) <= 1:
            continue
        findings.append(
            VerificationFinding(
                severity=VerificationSeverity.HIGH,
                category=VerificationFindingCategory.INTERFACE_CONFLICT,
                message="One enabled interface signal is assigned to multiple pins.",
                evidence=(
                    f"observed: interface_id={interface_id}",
                    f"observed: signal={signal}",
                    f"observed: pin_count={len(pins)}",
                    "observed: pin_sample=" + ",".join(sorted(pins)[:8]),
                ),
                recommendation=(
                    "Select one validated pin assignment for the enabled interface signal."
                ),
            )
        )
    return tuple(findings)


def _power_findings(
    subject: HardwareVerificationSubject,
) -> tuple[VerificationFinding, ...]:
    findings: list[VerificationFinding] = []
    for connection in subject.power_connections:
        overlap_min = max(connection.supply_min_v, connection.required_min_v)
        overlap_max = min(connection.supply_max_v, connection.required_max_v)
        if overlap_min <= overlap_max:
            continue
        findings.append(
            VerificationFinding(
                severity=VerificationSeverity.HIGH,
                category=VerificationFindingCategory.POWER_CONSTRAINT,
                message="The proposed supply and load voltage ranges do not overlap.",
                evidence=(
                    f"observed: source={connection.source_reference_id}",
                    f"observed: load={connection.load_reference_id}",
                    (
                        "observed: supply_range_v="
                        f"{connection.supply_min_v}-{connection.supply_max_v}"
                    ),
                    (
                        "observed: required_range_v="
                        f"{connection.required_min_v}-{connection.required_max_v}"
                    ),
                ),
                recommendation=(
                    "Confirm the power-domain evidence and choose a compatible supply range."
                ),
            )
        )
    return tuple(findings)
