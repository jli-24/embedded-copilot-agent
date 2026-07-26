from __future__ import annotations

from embedded_copilot.reasoning_runtime.contracts import (
    RiskCandidate,
    RuleResult,
    SupportingReference,
)
from embedded_copilot.reasoning_runtime.rules.context import RuleContext


def project_risks(
    context: RuleContext,
    results: tuple[RuleResult, ...],
) -> tuple[RiskCandidate, ...]:
    active = tuple(item for item in results if item.triggered)
    risks: list[RiskCandidate] = []
    if _result(active, "missing_context") is not None:
        risks.append(
            RiskCandidate(
                category="context_completeness",
                description=(
                    "No referenced engineering context is available; guidance remains "
                    "under-constrained."
                ),
                severity="high",
            )
        )

    component_results = tuple(
        item
        for item in active
        if item.rule_id
        in {"missing_component_candidate", "multiple_component_candidates"}
    )
    if component_results:
        risks.append(
            RiskCandidate(
                category="component_identity",
                description=(
                    "Component identity candidates require engineer confirmation before "
                    "use."
                ),
                severity="medium",
                supporting_references=_supporting(context, component_results),
            )
        )

    interface_result = _result(active, "interface_review_required")
    if interface_result is not None:
        risks.append(
            RiskCandidate(
                category="interface_compatibility",
                description=(
                    "Interface candidates require electrical and protocol compatibility "
                    "verification."
                ),
                severity="medium",
                supporting_references=_supporting(context, (interface_result,)),
            )
        )

    firmware_result = _result(
        active,
        "firmware_configuration_review_required",
    )
    if firmware_result is not None:
        risks.append(
            RiskCandidate(
                category="firmware_configuration",
                description=(
                    "Firmware configuration cannot be validated from file structure "
                    "summaries."
                ),
                severity="medium",
                supporting_references=_supporting(context, (firmware_result,)),
            )
        )

    vision_result = _result(active, "visual_observation_review_required")
    if vision_result is not None:
        risks.append(
            RiskCandidate(
                category="visual_interpretation",
                description=(
                    "Vision references require engineer-reviewed observations before use."
                ),
                severity="medium",
                supporting_references=_supporting(context, (vision_result,)),
            )
        )
    return tuple(risks)


def _result(
    results: tuple[RuleResult, ...],
    rule_id: str,
) -> RuleResult | None:
    return next((item for item in results if item.rule_id == rule_id), None)


def _supporting(
    context: RuleContext,
    results: tuple[RuleResult, ...],
) -> tuple[SupportingReference, ...]:
    reasons: list[tuple[str, str]] = []
    for result in results:
        for reference in result.references:
            key = reference.casefold()
            if any(item[0].casefold() == key for item in reasons):
                continue
            reasons.append((reference, result.reason))
    return tuple(
        SupportingReference(
            reference_id=reference,
            source_type=context.source_type_for(reference),
            reason=reason,
        )
        for reference, reason in reasons
    )
