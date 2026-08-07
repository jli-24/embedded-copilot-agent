from __future__ import annotations

import copy

from .contracts import (
    ApprovedMemoryProjectionPort,
    DatasheetMetadataProjectionPort,
    EngineeringContextProviderPort,
    EngineeringGraphProjectionPort,
    KnowledgeEvolutionProjectionPort,
)
from .exceptions import EngineeringContextRejected, EngineeringContextUnavailable
from .fusion import fuse_projections
from .models import (
    ApprovedMemoryProjection,
    ContextSourceReference,
    EngineeringContextItem,
    EngineeringContextQuery,
    EngineeringContextSnapshot,
    VerifiedKnowledgeProjection,
    validate_graph,
)
from .policy import ContextCategory, ContextVerificationStatus
from .retrieval import retrieve_items


class EngineeringContextService(EngineeringContextProviderPort):
    """Read-only assembly of approved and verified context projections."""

    __slots__ = (
        "_datasheet_port",
        "_graph_port",
        "_knowledge_port",
        "_memory_port",
    )

    def __init__(
        self,
        *,
        memory_port: ApprovedMemoryProjectionPort,
        graph_port: EngineeringGraphProjectionPort,
        knowledge_port: KnowledgeEvolutionProjectionPort | None = None,
        datasheet_port: DatasheetMetadataProjectionPort | None = None,
    ) -> None:
        if not isinstance(memory_port, ApprovedMemoryProjectionPort):
            raise TypeError("approved memory projection port is invalid")
        if not isinstance(graph_port, EngineeringGraphProjectionPort):
            raise TypeError("graph projection port is invalid")
        if knowledge_port is not None and not isinstance(
            knowledge_port, KnowledgeEvolutionProjectionPort
        ):
            raise TypeError("knowledge projection port is invalid")
        if datasheet_port is not None and not isinstance(
            datasheet_port, DatasheetMetadataProjectionPort
        ):
            raise TypeError("datasheet projection port is invalid")
        self._memory_port = memory_port
        self._graph_port = graph_port
        self._knowledge_port = knowledge_port
        self._datasheet_port = datasheet_port

    def get_context(
        self, query: EngineeringContextQuery
    ) -> EngineeringContextSnapshot | None:
        if type(query) is not EngineeringContextQuery:
            raise TypeError("context query must be a typed projection")
        checked_query = EngineeringContextQuery.model_validate(copy.deepcopy(query))
        try:
            memories = self._memory_port.list_approved(
                copy.deepcopy(checked_query.project_id)
            )
            if type(memories) is not tuple:
                raise ValueError("approved memory projection must be a tuple")
            checked_memories = tuple(
                ApprovedMemoryProjection.model_validate(copy.deepcopy(value))
                for value in memories
            )
            if any(
                value.status != "APPROVED"
                or value.project_id != checked_query.project_id
                for value in checked_memories
            ):
                raise ValueError("approved memory projection is invalid")

            graph_value = self._graph_port.project(
                copy.deepcopy(checked_query.project_id)
            )
            graph: object | None = None
            if graph_value is not None:
                graph = validate_graph(copy.deepcopy(graph_value))
                if graph.project_id != checked_query.project_id:
                    raise ValueError("graph projection is invalid")

            knowledge: tuple[VerifiedKnowledgeProjection, ...] = ()
            if self._knowledge_port is not None:
                raw_knowledge = self._knowledge_port.get_snapshot(
                    copy.deepcopy(checked_query.project_id)
                )
                if type(raw_knowledge) is not tuple:
                    raise ValueError("knowledge projection must be a tuple")
                knowledge = tuple(
                    VerifiedKnowledgeProjection.model_validate(copy.deepcopy(value))
                    for value in raw_knowledge
                )

            datasheet = ()
            if self._datasheet_port is not None:
                raw_datasheet = self._datasheet_port.list_metadata(
                    copy.deepcopy(checked_query.project_id),
                    copy.deepcopy(checked_query.query),
                )
                if type(raw_datasheet) is not tuple:
                    raise ValueError("datasheet projection must be a tuple")
                from .models import DatasheetMetadataProjection

                datasheet = tuple(
                    DatasheetMetadataProjection.model_validate(copy.deepcopy(value))
                    for value in raw_datasheet
                )

            fusion = fuse_projections(
                project_id=checked_query.project_id,
                memories=checked_memories,
                graph=graph,
                knowledge=knowledge,
                datasheet=datasheet,
            )
            if not fusion.items:
                return None
            selected = retrieve_items(
                items=fusion.items,
                graph=graph,
                query=checked_query,
            )
            if not selected:
                return None
            return _build_snapshot(
                query=checked_query,
                selected=selected,
                sources=fusion.sources,
                graph=graph,
                memory_fingerprint=fusion.memory_fingerprint,
            )
        except EngineeringContextRejected:
            raise
        except (TypeError, ValueError) as error:
            raise EngineeringContextRejected() from error
        except Exception as error:
            raise EngineeringContextUnavailable() from error


def _empty_projection_fingerprint(label: str) -> str:
    from hashlib import sha256

    return "sha256:" + sha256(label.encode("utf-8")).hexdigest()


def _category_values(
    selected: tuple[EngineeringContextItem, ...], category: ContextCategory
) -> tuple[EngineeringContextItem, ...]:
    return tuple(item for item in selected if item.category is category)


def _status(selected: tuple[EngineeringContextItem, ...]) -> str:
    statuses = {item.verification_status for item in selected}
    if statuses == {ContextVerificationStatus.APPROVED.value}:
        return ContextVerificationStatus.APPROVED.value
    if statuses <= {
        ContextVerificationStatus.APPROVED.value,
        ContextVerificationStatus.VERIFIED.value,
    }:
        return ContextVerificationStatus.VERIFIED.value
    return ContextVerificationStatus.PROJECTED.value


def _build_snapshot(
    *,
    query: EngineeringContextQuery,
    selected: tuple[EngineeringContextItem, ...],
    sources: tuple[ContextSourceReference, ...],
    graph: object | None,
    memory_fingerprint: str,
) -> EngineeringContextSnapshot:
    graph_fingerprint = (
        graph.fingerprint if graph is not None else _empty_projection_fingerprint("graph")
    )
    return EngineeringContextSnapshot.create(
        project_id=query.project_id,
        query=query.query,
        requirements=_category_values(selected, ContextCategory.REQUIREMENT),
        decisions=_category_values(selected, ContextCategory.DECISION),
        constraints=_category_values(selected, ContextCategory.CONSTRAINT),
        historical_problems=_category_values(
            selected, ContextCategory.HISTORICAL_PROBLEM
        ),
        solutions=_category_values(selected, ContextCategory.SOLUTION),
        components=_category_values(selected, ContextCategory.COMPONENT),
        interfaces=_category_values(selected, ContextCategory.INTERFACE),
        sources=sources,
        confidence=min(item.confidence for item in selected),
        verification_status=_status(selected),
        graph_fingerprint=graph_fingerprint,
        memory_fingerprint=memory_fingerprint,
    )


__all__ = ("EngineeringContextService",)
