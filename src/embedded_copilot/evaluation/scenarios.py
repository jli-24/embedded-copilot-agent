from __future__ import annotations

import copy

from embedded_copilot.benchmark.datasets.synthetic import (
    create_synthetic_embedded_copilot_integration_dataset,
)
from embedded_copilot.benchmark.models import BenchmarkCase


_AGENT_NAMES = frozenset(
    {"FirmwareAgent", "HardwareAgent", "PCBAgent", "DebugAgent"}
)


def create_default_evaluation_dataset():
    return create_synthetic_embedded_copilot_integration_dataset()


def expected_agents(case: BenchmarkCase) -> tuple[str, ...]:
    if not isinstance(case, BenchmarkCase) or case.category != "end_to_end":
        raise ValueError("evaluation scenario is invalid")
    metadata = copy.deepcopy(case.metadata)
    if metadata.get("fixture_kind") != "synthetic":
        raise ValueError("evaluation scenario is invalid")
    expected = copy.deepcopy(case.expected)
    if set(expected) != {"agents", "capabilities"}:
        raise ValueError("evaluation scenario is invalid")
    raw_agents = expected.get("agents")
    if not isinstance(raw_agents, list) or not raw_agents:
        raise ValueError("evaluation scenario is invalid")
    agents = tuple(raw_agents)
    if (
        any(not isinstance(agent, str) or agent not in _AGENT_NAMES for agent in agents)
        or len(agents) != len(set(agents))
    ):
        raise ValueError("evaluation scenario is invalid")
    return agents
