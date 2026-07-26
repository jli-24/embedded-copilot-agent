from __future__ import annotations

from embedded_copilot.reasoning_runtime.contracts import NextStep, RuleResult


def plan_next_steps(results: tuple[RuleResult, ...]) -> tuple[NextStep, ...]:
    active = {item.rule_id for item in results if item.triggered}
    steps: list[NextStep] = []
    if "missing_context" in active:
        steps.append(
            NextStep(
                action="Provide relevant engineering references",
                reason=(
                    "Deterministic review requires safe referenced context before "
                    "engineer validation."
                ),
            )
        )
    if active & {
        "missing_component_candidate",
        "multiple_component_candidates",
    }:
        steps.append(
            NextStep(
                action="Confirm the target component identity",
                reason=(
                    "Component candidates must be resolved against their source "
                    "documents."
                ),
            )
        )
    if "interface_review_required" in active:
        steps.append(
            NextStep(
                action="Verify interface candidate compatibility",
                reason=(
                    "Electrical and protocol requirements require engineer comparison."
                ),
            )
        )
    if "firmware_configuration_review_required" in active:
        steps.append(
            NextStep(
                action="Inspect firmware configuration against verified requirements",
                reason=(
                    "File structure summaries do not establish configuration behavior."
                ),
            )
        )
    if "visual_observation_review_required" in active:
        steps.append(
            NextStep(
                action="Obtain engineer-reviewed visual observations",
                reason=(
                    "A vision reference alone does not establish a validated finding."
                ),
            )
        )
    if not steps:
        steps.append(
            NextStep(
                action="Review the available candidates with an engineer",
                reason="Candidate context remains guidance until engineer validation.",
            )
        )
    return tuple(steps)
