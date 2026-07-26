from __future__ import annotations

from embedded_copilot.reasoning_runtime.contracts import (
    ReasoningContextSnapshot,
    ReasoningSummary,
)


def analyze_context(snapshot: ReasoningContextSnapshot) -> ReasoningSummary:
    datasheet_count = len(snapshot.datasheet_candidates)
    file_count = len(snapshot.file_summaries)
    vision_count = len(snapshot.vision_refs)
    summary = (
        f"The snapshot contains {datasheet_count} datasheet candidate source(s), "
        f"{file_count} file structure summary source(s), and {vision_count} vision "
        "reference source(s) for engineer review."
    )
    assumptions = [
        "The supplied task intent represents the engineer's current review goal."
    ]
    if datasheet_count:
        assumptions.append(
            "Datasheet-derived values remain unverified candidates until engineer "
            "validation."
        )
    if file_count:
        assumptions.append(
            "File summaries describe structure only and do not validate implementation "
            "behavior."
        )
    if vision_count:
        assumptions.append(
            "Vision references identify inputs only and do not establish visual findings."
        )
    if not (datasheet_count or file_count or vision_count):
        assumptions.append(
            "No referenced engineering context was available for this analysis."
        )
    return ReasoningSummary(
        summary=summary,
        confidence=confidence_for(snapshot),
        assumptions=tuple(assumptions),
    )


def confidence_for(snapshot: ReasoningContextSnapshot) -> str:
    has_candidate = any(
        item.component_candidate is not None or item.interfaces or item.sections
        for item in snapshot.datasheet_candidates
    )
    return "medium" if has_candidate else "low"
