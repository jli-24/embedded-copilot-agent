from __future__ import annotations

import copy
import inspect

from pydantic import ValidationError

from .context import (
    MemoryContext,
    MemoryContextEvidence,
    MemoryRankingBreakdown,
    MemoryRetrievalRequest,
    MemoryTrustBasis,
)
from .exceptions import (
    MemoryPermissionDenied,
    MemoryRetrievalRequestRejected,
    MemoryRetrievalUnavailable,
)
from .fingerprint import canonical_data_fingerprint
from .models import (
    EngineeringMemoryHistoryPage,
    EngineeringMemorySnapshot,
    GetHistoryRequest,
    GetVerifiedSnapshotRequest,
    MemorySnapshotType,
)
from .ports import EngineeringMemoryPort
from .read_projection import (
    VerifiedMemoryReadProjection,
    project_verified_memory_read,
)

_EMPTY_FINGERPRINT = "sha256:" + "0" * 64
_HISTORY_PAGE_LIMIT = 100
_MAX_HISTORY_PAGES = 1000


def _child_request_id(
    request: MemoryRetrievalRequest,
    *,
    stage: str,
    page: int,
) -> str:
    fingerprint = canonical_data_fingerprint(
        {
            "request": request.model_dump(mode="json"),
            "stage": stage,
            "page": page,
        }
    )
    return "mr-" + fingerprint.removeprefix("sha256:")[:32]


def _empty_context(request: MemoryRetrievalRequest) -> MemoryContext:
    return MemoryContext(
        request_id=request.request_id,
        project_id=request.project_id,
        memory_id=request.memory_id,
        aggregate_revision=0,
        domains=request.domains,
        records=(),
        evidence=(),
        confidence=0.0,
        source_snapshot_fingerprint=_EMPTY_FINGERPRINT,
        context_fingerprint=_EMPTY_FINGERPRINT,
    )


def _execute(memory_port: EngineeringMemoryPort, request):
    before = request.model_dump_json()
    result = memory_port.execute(request)
    if request.model_dump_json() != before:
        raise ValueError("memory port mutated request")
    return result


def _verified_snapshot(
    memory_port: EngineeringMemoryPort,
    request: MemoryRetrievalRequest,
) -> EngineeringMemorySnapshot:
    child_id = _child_request_id(request, stage="snapshot", page=0)
    query = GetVerifiedSnapshotRequest(
        request_id=child_id,
        project_id=request.project_id,
        memory_id=request.memory_id,
        caller=request.caller,
        requested_at=request.requested_at,
    )
    result = EngineeringMemorySnapshot.model_validate(
        copy.deepcopy(_execute(memory_port, query))
    )
    if (
        result.request_id != child_id
        or result.snapshot_type is not MemorySnapshotType.VERIFIED
        or result.project_id != request.project_id
        or result.memory_id != request.memory_id
    ):
        raise ValueError("verified snapshot binding is invalid")
    return result


def _history_pages(
    memory_port: EngineeringMemoryPort,
    request: MemoryRetrievalRequest,
    *,
    snapshot: EngineeringMemorySnapshot,
) -> tuple[EngineeringMemoryHistoryPage, ...]:
    pages: list[EngineeringMemoryHistoryPage] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    for page_number in range(_MAX_HISTORY_PAGES):
        child_id = _child_request_id(
            request,
            stage="history",
            page=page_number,
        )
        query = GetHistoryRequest(
            request_id=child_id,
            project_id=request.project_id,
            memory_id=request.memory_id,
            caller=request.caller,
            requested_at=request.requested_at,
            cursor=cursor,
            limit=_HISTORY_PAGE_LIMIT,
        )
        page = EngineeringMemoryHistoryPage.model_validate(
            copy.deepcopy(_execute(memory_port, query))
        )
        if (
            page.request_id != child_id
            or page.project_id != request.project_id
            or page.memory_id != request.memory_id
            or page.aggregate_revision != snapshot.aggregate_revision
        ):
            raise ValueError("history page binding is invalid")
        pages.append(page)
        if not page.has_more:
            return tuple(pages)
        next_cursor = page.next_cursor
        if (
            next_cursor is None
            or not next_cursor.startswith(
                f"revision:{snapshot.aggregate_revision}:offset:"
            )
            or next_cursor in seen_cursors
        ):
            raise ValueError("history cursor binding is invalid")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    raise ValueError("history pagination is unbounded")


def _neutral_ranking() -> MemoryRankingBreakdown:
    return MemoryRankingBreakdown(
        verification_millis=0,
        domain_millis=0,
        usage_millis=0,
        recency_millis=0,
        total_millis=0,
        relevance_score=0.0,
    )


def _evidence(
    projection: VerifiedMemoryReadProjection,
    *,
    record,
) -> MemoryContextEvidence:
    verification_confidence = (
        projection.confidence
        if projection.trust_basis is MemoryTrustBasis.VERIFICATION
        else None
    )
    return MemoryContextEvidence(
        record_id=projection.record_id,
        memory_type=projection.memory_type,
        logical_key=projection.logical_key,
        trust_basis=projection.trust_basis,
        verification_subject=projection.verification_subject,
        verification_confidence=verification_confidence,
        provenance_source_type=record.provenance.source_type,
        provenance_reference=record.provenance.source_reference,
        last_transition_at=projection.last_transition_at,
        ranking=_neutral_ranking(),
    )


def _context(
    request: MemoryRetrievalRequest,
    *,
    snapshot: EngineeringMemorySnapshot,
    projections: tuple[VerifiedMemoryReadProjection, ...],
) -> MemoryContext:
    selected_records = snapshot.records[: request.limit]
    selected_projections = projections[: request.limit]
    evidence = tuple(
        _evidence(projection, record=record)
        for record, projection in zip(
            selected_records,
            selected_projections,
            strict=True,
        )
    )
    confidence = (
        min(
            1.0
            if item.trust_basis is MemoryTrustBasis.VERIFICATION
            else 0.5
            for item in evidence
        )
        if evidence
        else 0.0
    )
    return MemoryContext(
        request_id=request.request_id,
        project_id=request.project_id,
        memory_id=request.memory_id,
        aggregate_revision=snapshot.aggregate_revision,
        domains=request.domains,
        records=selected_records,
        evidence=evidence,
        confidence=confidence,
        source_snapshot_fingerprint=snapshot.snapshot_fingerprint,
        context_fingerprint=snapshot.snapshot_fingerprint,
    )


class EngineeringMemoryRetriever:
    __slots__ = ("__memory_port",)

    def __init__(self, memory_port: EngineeringMemoryPort) -> None:
        raise TypeError(
            "EngineeringMemoryRetriever must be created by its factory"
        )

    @classmethod
    def _compose(
        cls,
        memory_port: EngineeringMemoryPort,
    ) -> EngineeringMemoryRetriever:
        instance = object.__new__(cls)
        object.__setattr__(instance, "_EngineeringMemoryRetriever__memory_port", memory_port)
        return instance

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("EngineeringMemoryRetriever is immutable")

    def retrieve(self, request: MemoryRetrievalRequest) -> MemoryContext:
        try:
            checked = MemoryRetrievalRequest.model_validate(copy.deepcopy(request))
        except (TypeError, ValueError, ValidationError):
            raise MemoryRetrievalRequestRejected() from None

        try:
            snapshot = _verified_snapshot(self.__memory_port, checked)
            snapshot_ids = tuple(item.record_id for item in snapshot.records)
            usage_ids = tuple(item.record_id for item in checked.usage_signals)
            if any(record_id not in snapshot_ids for record_id in usage_ids):
                raise MemoryRetrievalRequestRejected()
            if not snapshot.records:
                return MemoryContext.model_validate(
                    copy.deepcopy(
                        _context(
                            checked,
                            snapshot=snapshot,
                            projections=(),
                        )
                    )
                )
            history_pages = _history_pages(
                self.__memory_port,
                checked,
                snapshot=snapshot,
            )
            projections = project_verified_memory_read(
                snapshot=snapshot,
                history_pages=history_pages,
                requested_at=checked.requested_at,
            )
            return MemoryContext.model_validate(
                copy.deepcopy(
                    _context(
                        checked,
                        snapshot=snapshot,
                        projections=projections,
                    )
                )
            )
        except MemoryPermissionDenied:
            return MemoryContext.model_validate(copy.deepcopy(_empty_context(checked)))
        except MemoryRetrievalRequestRejected:
            raise MemoryRetrievalRequestRejected() from None
        except Exception:
            raise MemoryRetrievalUnavailable() from None


def create_engineering_memory_retriever(
    *,
    memory_port: EngineeringMemoryPort,
) -> EngineeringMemoryRetriever:
    execute = getattr(memory_port, "execute", None)
    if (
        not isinstance(memory_port, EngineeringMemoryPort)
        or not callable(execute)
        or inspect.iscoroutinefunction(execute)
    ):
        raise TypeError("memory_port must implement synchronous EngineeringMemoryPort")
    return EngineeringMemoryRetriever._compose(memory_port)
