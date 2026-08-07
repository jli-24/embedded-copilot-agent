from __future__ import annotations

import copy
import hashlib
import json
from typing import NamedTuple

from .models import (
    ApprovedMemoryProjection,
    ContextSourceReference,
    DatasheetMetadataProjection,
    EngineeringContextItem,
    VerifiedKnowledgeProjection,
)
from .policy import ContextCategory, ContextPolicy, ContextSourceType


class FusionResult(NamedTuple):
    items: tuple[EngineeringContextItem, ...]
    sources: tuple[ContextSourceReference, ...]
    memory_fingerprint: str


class ContextFusionService:
    """Small facade around deterministic projection fusion."""

    def fuse(self, **kwargs: object) -> FusionResult:
        return fuse_projections(**kwargs)


def _projection_fingerprint(values: tuple[str, ...], label: str) -> str:
    payload = json.dumps(
        {"label": label, "values": tuple(sorted(values))},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _source(
    *,
    source_type: ContextSourceType,
    source_id: str,
    source_reference: str,
    source_fingerprint: str,
    verification_status: str,
    confidence: float,
) -> ContextSourceReference:
    return ContextSourceReference.create(
        source_type=source_type,
        source_id=source_id,
        source_reference=source_reference,
        source_fingerprint=source_fingerprint,
        verification_status=verification_status,
        confidence=confidence,
    )


def _item(
    *,
    item_id: str,
    project_id: str,
    category,
    entity_name: str,
    summary: str,
    source: ContextSourceReference,
    confidence: float,
    verification_status: str,
) -> EngineeringContextItem:
    return EngineeringContextItem.create(
        item_id=item_id,
        project_id=project_id,
        category=category,
        entity_name=entity_name,
        summary=summary,
        source_references=(source,),
        confidence=confidence,
        verification_status=verification_status,
    )


def _memory_projection(
    value: ApprovedMemoryProjection,
) -> tuple[EngineeringContextItem | None, ContextSourceReference]:
    source = _source(
        source_type=ContextSourceType.ENGINEERING_MEMORY,
        source_id=f"memory-{value.memory_id}",
        source_reference=value.source_reference,
        source_fingerprint=value.fingerprint,
        verification_status="APPROVED",
        confidence=value.confidence,
    )
    category = ContextPolicy.category_for_memory_type(value.memory_type)
    if category is None:
        return None, source
    return (
        _item(
            item_id=f"memory-{value.memory_id}",
            project_id=value.project_id,
            category=category,
            entity_name=value.memory_id,
            summary=value.summary,
            source=source,
            confidence=value.confidence,
            verification_status="APPROVED",
        ),
        source,
    )


def _graph_projection(
    graph: object,
) -> tuple[tuple[EngineeringContextItem, ...], tuple[ContextSourceReference, ...]]:
    items: list[EngineeringContextItem] = []
    sources: list[ContextSourceReference] = []
    for node in graph.nodes:
        source = _source(
            source_type=ContextSourceType.KNOWLEDGE_GRAPH,
            source_id=f"graph-{node.node_id}",
            source_reference=node.source_reference,
            source_fingerprint=node.fingerprint,
            verification_status=node.verification_status,
            confidence=node.confidence,
        )
        sources.append(source)
        category = ContextPolicy.category_for_graph_type(node.node_type.value)
        if category is not None:
            items.append(
                _item(
                    item_id=node.node_id,
                    project_id=node.project_id,
                    category=category,
                    entity_name=node.entity_name,
                    summary=node.summary,
                    source=source,
                    confidence=node.confidence,
                    verification_status=node.verification_status,
                )
            )
    return tuple(items), tuple(sources)


def _knowledge_projection(
    value: VerifiedKnowledgeProjection,
) -> tuple[EngineeringContextItem, ContextSourceReference]:
    source = _source(
        source_type=ContextSourceType.KNOWLEDGE_EVOLUTION,
        source_id=value.source_id,
        source_reference=value.source_reference,
        source_fingerprint=value.source_fingerprint,
        verification_status=value.verification_status,
        confidence=value.confidence,
    )
    return (
        _item(
            item_id=f"knowledge-{value.source_id}",
            project_id=value.project_id,
            category=value.category,
            entity_name=value.entity_name,
            summary=value.summary,
            source=source,
            confidence=value.confidence,
            verification_status=value.verification_status,
        ),
        source,
    )


def _datasheet_projection(
    value: DatasheetMetadataProjection,
) -> tuple[EngineeringContextItem, ContextSourceReference]:
    source = _source(
        source_type=ContextSourceType.DATASHEET_METADATA,
        source_id=value.source_id,
        source_reference=value.source_reference,
        source_fingerprint=value.source_fingerprint,
        verification_status=value.verification_status,
        confidence=value.confidence,
    )
    return (
        _item(
            item_id=f"datasheet-{value.source_id}",
            project_id=value.project_id,
            category=ContextCategory.COMPONENT,
            entity_name=value.component,
            summary=value.property,
            source=source,
            confidence=value.confidence,
            verification_status=value.verification_status,
        ),
        source,
    )


def fuse_projections(
    *,
    project_id: str,
    memories: tuple[ApprovedMemoryProjection, ...],
    graph: object | None,
    knowledge: tuple[VerifiedKnowledgeProjection, ...] = (),
    datasheet: tuple[DatasheetMetadataProjection, ...] = (),
) -> FusionResult:
    items: list[EngineeringContextItem] = []
    sources: list[ContextSourceReference] = []
    memory_fingerprints: list[str] = []

    for value in copy.deepcopy(memories):
        checked = ApprovedMemoryProjection.model_validate(value)
        if checked.project_id != project_id or checked.status != "APPROVED":
            raise ValueError("approved memory projection binding is invalid")
        item, source = _memory_projection(checked)
        memory_fingerprints.append(checked.fingerprint)
        sources.append(source)
        if item is not None:
            items.append(item)

    if graph is not None:
        graph_items, graph_sources = _graph_projection(graph)
        if graph.project_id != project_id:
            raise ValueError("graph projection binding is invalid")
        items.extend(graph_items)
        sources.extend(graph_sources)

    for value in copy.deepcopy(knowledge):
        checked = VerifiedKnowledgeProjection.model_validate(value)
        if checked.project_id != project_id:
            raise ValueError("knowledge projection binding is invalid")
        item, source = _knowledge_projection(checked)
        items.append(item)
        sources.append(source)

    for value in copy.deepcopy(datasheet):
        checked = DatasheetMetadataProjection.model_validate(value)
        if checked.project_id != project_id:
            raise ValueError("datasheet projection binding is invalid")
        item, source = _datasheet_projection(checked)
        items.append(item)
        sources.append(source)

    item_by_id: dict[str, EngineeringContextItem] = {}
    for item in items:
        previous = item_by_id.get(item.item_id)
        if previous is None:
            item_by_id[item.item_id] = item
            continue
        references = {
            reference.source_id: reference
            for reference in (*previous.source_references, *item.source_references)
        }
        item_by_id[item.item_id] = EngineeringContextItem.create(
            item_id=previous.item_id,
            project_id=previous.project_id,
            category=previous.category,
            entity_name=previous.entity_name,
            summary=previous.summary,
            source_references=tuple(
                references[key] for key in sorted(references)
            ),
            confidence=min(previous.confidence, item.confidence),
            verification_status=(
                "APPROVED"
                if previous.verification_status == item.verification_status == "APPROVED"
                else "VERIFIED"
                if {previous.verification_status, item.verification_status}
                <= {"APPROVED", "VERIFIED"}
                else "PROJECTED"
            ),
        )
    source_by_id = {source.source_id: source for source in sources}
    return FusionResult(
        items=tuple(item_by_id[key] for key in sorted(item_by_id)),
        sources=tuple(source_by_id[key] for key in sorted(source_by_id)),
        memory_fingerprint=_projection_fingerprint(
            tuple(memory_fingerprints), "engineering-memory"
        ),
    )


__all__ = ("ContextFusionService", "FusionResult", "fuse_projections")
