from __future__ import annotations

from collections.abc import Callable

from embedded_copilot.reasoning_runtime.contracts import RuleResult
from embedded_copilot.reasoning_runtime.rules.component_rules import (
    missing_component_candidate,
    multiple_component_candidates,
)
from embedded_copilot.reasoning_runtime.rules.context import RuleContext
from embedded_copilot.reasoning_runtime.rules.context_rules import missing_context
from embedded_copilot.reasoning_runtime.rules.firmware_rules import (
    firmware_configuration_review_required,
)
from embedded_copilot.reasoning_runtime.rules.interface_rules import (
    interface_review_required,
)
from embedded_copilot.reasoning_runtime.rules.vision_rules import (
    visual_observation_review_required,
)

Rule = Callable[[RuleContext], RuleResult]

RULES: tuple[Rule, ...] = (
    missing_context,
    missing_component_candidate,
    multiple_component_candidates,
    interface_review_required,
    firmware_configuration_review_required,
    visual_observation_review_required,
)


def evaluate_rules(context: RuleContext) -> tuple[RuleResult, ...]:
    return tuple(rule(context) for rule in RULES)
