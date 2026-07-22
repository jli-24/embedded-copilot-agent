from __future__ import annotations

from embedded_copilot.knowledge.entity import ExtractedEntities


GENERIC_CHIP = "__generic__"


def build_metadata_filter(entities: ExtractedEntities) -> dict[str, object] | None:
    if entities.chip is None:
        return None
    return {
        "$or": [
            {"chip": entities.chip},
            {"chip": GENERIC_CHIP},
        ]
    }
