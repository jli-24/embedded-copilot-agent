from __future__ import annotations

import copy
from collections.abc import Sequence

from embedded_copilot.debug.exceptions import DebugPlanningError
from embedded_copilot.debug.models import (
    DebugEvidence,
    DebugFinding,
    DebugPlan,
    DebugRequest,
)


def _stable_unique(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


class DebugPlanner:
    """Create a deterministic, non-executing diagnostic plan."""

    def plan(
        self,
        request: DebugRequest,
        findings: Sequence[DebugFinding],
        documents: Sequence[DebugEvidence],
    ) -> DebugPlan:
        if not findings:
            raise DebugPlanningError("debug planning requires at least one finding")
        actions = _stable_unique([finding.recommendation for finding in findings])
        knowledge_sources = _stable_unique([item.source for item in documents])
        source_count = len(knowledge_sources)
        limitation = (
            "no knowledge evidence was retrieved."
            if source_count == 0
            else "knowledge evidence is advisory and does not verify a root cause."
        )
        return DebugPlan(
            project_name=request.project_name or "debug_project",
            platform=request.platform,
            error_type=request.error_type,
            findings=copy.deepcopy(list(findings)),
            actions=actions,
            rationale=(
                f"Deterministic debug rules produced {len(findings)} finding(s) "
                f"using {source_count} knowledge source(s); {limitation}"
            ),
            metadata={
                "analysis_mode": (
                    "knowledge_augmented"
                    if documents
                    else "unverified_rule_based"
                ),
                "finding_count": len(findings),
                "knowledge_source_count": source_count,
                "knowledge_sources": knowledge_sources,
            },
        )
