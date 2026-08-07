from __future__ import annotations

from embedded_copilot.engineering_context import (
    ContextCategory,
    ContextSourceReference,
    ContextSourceType,
    EngineeringContextItem,
)
from embedded_copilot.engineering_context.ranking import rank_items


def _item(item_id: str, entity_name: str, summary: str) -> EngineeringContextItem:
    source = ContextSourceReference.create(
        source_type=ContextSourceType.ENGINEERING_MEMORY,
        source_id=f"memory-{item_id}",
        source_reference=f"decision:{item_id}",
        source_fingerprint="sha256:" + "a" * 64,
        verification_status="APPROVED",
        confidence=0.8,
    )
    return EngineeringContextItem.create(
        item_id=item_id,
        project_id="project-1",
        category=ContextCategory.DECISION,
        entity_name=entity_name,
        summary=summary,
        source_references=(source,),
        confidence=0.8,
        verification_status="APPROVED",
    )


def test_ranking_uses_exact_entity_then_overlap_then_stable_id() -> None:
    values = (
        _item("item-b", "camera", "camera interface"),
        _item("item-a", "camera", "camera interface"),
        _item("item-c", "sensor", "temperature sensor"),
    )
    ranked = rank_items(values, "camera", None, 3)
    assert tuple(item.item_id for item in ranked) == (
        "item-a",
        "item-b",
        "item-c",
    )
