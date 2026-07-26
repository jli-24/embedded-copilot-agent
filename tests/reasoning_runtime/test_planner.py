from __future__ import annotations

from embedded_copilot.reasoning_runtime import RuleResult
from embedded_copilot.reasoning_runtime.capabilities import active_capabilities
from embedded_copilot.reasoning_runtime.planning import plan_next_steps


def _rule(rule_id: str, source: str, *, triggered: bool) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        rule_source=source,  # type: ignore[arg-type]
        triggered=triggered,
        references=(),
        reason="Fixed deterministic rule result.",
    )


def test_planner_maps_only_triggered_rule_results_in_stable_order() -> None:
    results = (
        _rule("missing_context", "context", triggered=False),
        _rule("missing_component_candidate", "component", triggered=True),
        _rule("interface_review_required", "interface", triggered=True),
        _rule(
            "firmware_configuration_review_required",
            "firmware",
            triggered=True,
        ),
        _rule("visual_observation_review_required", "vision", triggered=True),
    )

    steps = plan_next_steps(results)

    assert tuple(item.action for item in steps) == (
        "Confirm the target component identity",
        "Verify interface candidate compatibility",
        "Inspect firmware configuration against verified requirements",
        "Obtain engineer-reviewed visual observations",
    )


def test_planner_has_safe_review_fallback_without_triggered_rules() -> None:
    steps = plan_next_steps((_rule("missing_context", "context", triggered=False),))

    assert tuple(item.action for item in steps) == (
        "Review the available candidates with an engineer",
    )


def test_capability_registry_has_stable_names_and_versions() -> None:
    capabilities = active_capabilities()

    assert tuple((item.name, item.version) for item in capabilities) == (
        ("context_analysis", "1.0"),
        ("risk_detection", "1.0"),
        ("verification_planning", "1.0"),
    )
    assert capabilities is active_capabilities()
