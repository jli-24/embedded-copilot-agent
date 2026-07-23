from __future__ import annotations

import re

from embedded_copilot.pcb.models import PCBIssue, PCBRequirement, PCBRuleEvaluation


def _contains(text: str, pattern: str) -> bool:
    return re.search(pattern, text, re.IGNORECASE) is not None


def _issue(
    rule_id: str,
    category: str,
    description: str,
    recommendation: str,
    evidence: str,
) -> PCBIssue:
    return PCBIssue(
        id=rule_id,
        category=category,
        severity="warning",
        description=description,
        recommendation=recommendation,
        evidence=[evidence],
        metadata={
            "rule_id": rule_id,
            "analysis_mode": "requirement_evidence_check",
        },
    )


class PCBRuleEngine:
    """Evaluate immutable PCB requirements with pure deterministic rules."""

    def evaluate(self, requirement: PCBRequirement) -> PCBRuleEvaluation:
        components = frozenset(requirement.components)
        interfaces = frozenset(requirement.interfaces)
        constraints = "\n".join(requirement.constraints)
        issues: list[PCBIssue] = []
        passed: list[str] = []

        if "Power" in components:
            passed.append("pcb-power-declaration")
        else:
            issues.append(
                _issue(
                    "pcb-power-declaration",
                    "power",
                    "The requirement does not declare a power design stage.",
                    "Declare the power architecture and verify it from authorized component documentation.",
                    "No canonical Power component is present in the PCB requirement.",
                )
            )

        if _contains(constraints, r"decoupl|bypass|去耦|旁路"):
            passed.append("pcb-power-decoupling")
        else:
            issues.append(
                _issue(
                    "pcb-power-decoupling",
                    "power",
                    "The requirement does not provide decoupling evidence.",
                    "Document decoupling considerations using authorized component guidance.",
                    "No decoupling or bypass declaration is present in the constraints.",
                )
            )

        high_speed = "High-speed signal" in components or _contains(
            constraints, r"high[- ]?speed|高速"
        )
        if high_speed:
            if _contains(constraints, r"(clock|时钟).*(rout|return path|走线|回流)"):
                passed.append("pcb-clock-high-speed")
            else:
                issues.append(
                    _issue(
                        "pcb-clock-high-speed",
                        "clock",
                        "High-speed or clock layout evidence is not declared.",
                        "Review clock routing and return-path continuity without assuming geometry or timing limits.",
                        "A high-speed requirement exists without explicit clock routing evidence.",
                    )
                )

        analog = "Analog" in components or "ADC" in interfaces
        if analog:
            if _contains(constraints, r"noise|isolat|filter|噪声|隔离|滤波"):
                passed.append("pcb-analog-isolation")
            else:
                issues.append(
                    _issue(
                        "pcb-analog-isolation",
                        "analog",
                        "Analog noise-isolation evidence is not declared.",
                        "Review ADC placement, filtering, and noise isolation using verified design constraints.",
                        "Analog or ADC usage exists without noise-isolation evidence.",
                    )
                )

        for interface in ("SPI", "UART", "I2C"):
            if interface not in interfaces:
                continue
            rule_id = f"pcb-communication-{interface.casefold()}"
            layout_pattern = (
                rf"{interface}.*(layout|rout|trace|pull[- ]?up|terminat|布局|走线|上拉|终端)"
            )
            if _contains(constraints, layout_pattern):
                passed.append(rule_id)
            else:
                issues.append(
                    _issue(
                        rule_id,
                        "communication",
                        f"{interface} layout evidence is not declared.",
                        f"Review {interface} routing and electrical constraints using authorized interface documentation.",
                        f"The {interface} interface is present without explicit layout evidence.",
                    )
                )

        if _contains(constraints, r"\bgnd\b|ground|接地|地平面|地完整"):
            passed.append("pcb-ground-integrity")
        else:
            issues.append(
                _issue(
                    "pcb-ground-integrity",
                    "ground",
                    "Ground-integrity evidence is not declared.",
                    "Review ground continuity and return paths without assuming a layer stack.",
                    "No GND or ground-integrity declaration is present in the constraints.",
                )
            )

        return PCBRuleEvaluation(issues=issues, passed_rules=passed)
