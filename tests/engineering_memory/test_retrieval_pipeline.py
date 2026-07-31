from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_memory.context import (
    MemoryDomain,
    MemoryRetrievalRequest,
    MemoryUsageSignal,
)
from embedded_copilot.engineering_memory.exceptions import (
    MemoryPermissionDenied,
    MemoryRetrievalRequestRejected,
    MemoryRetrievalUnavailable,
)
from embedded_copilot.engineering_memory.models import (
    EngineeringMemoryHistoryPage,
    EngineeringMemorySnapshot,
    GetHistoryRequest,
    GetVerifiedSnapshotRequest,
    MemoryStatus,
)
from embedded_copilot.engineering_memory.retrieval import (
    EngineeringMemoryRetriever,
    create_engineering_memory_retriever,
)
from embedded_copilot.verification_agent import VerificationStatus

from .test_verified_read_projection import (
    REQUESTED_AT,
    _candidate_record,
    _history_page,
    _snapshot,
    _snapshot_record,
    _terminal_record,
    _verification_record,
)


class _MemoryPort:
    def __init__(
        self,
        *,
        snapshot: object,
        history_pages: tuple[object, ...] = (),
        failure: Exception | None = None,
        mutate: Callable[[object], None] | None = None,
    ) -> None:
        self._snapshot = snapshot
        self._history_pages = history_pages
        self._failure = failure
        self._mutate = mutate
        self.calls: list[object] = []

    def execute(self, request: object) -> object:
        self.calls.append(request)
        if self._mutate is not None:
            self._mutate(request)
        if self._failure is not None:
            raise self._failure
        if isinstance(request, GetVerifiedSnapshotRequest):
            if isinstance(self._snapshot, EngineeringMemorySnapshot):
                return self._snapshot.model_copy(
                    update={"request_id": request.request_id}
                )
            return self._snapshot
        if isinstance(request, GetHistoryRequest):
            page_index = sum(
                isinstance(item, GetHistoryRequest) for item in self.calls
            ) - 1
            page = self._history_pages[page_index]
            if isinstance(page, EngineeringMemoryHistoryPage):
                return page.model_copy(update={"request_id": request.request_id})
            return page
        raise AssertionError("unexpected memory request")


class _AsyncMemoryPort:
    async def execute(self, request: object) -> object:
        return request


def _request(
    *,
    limit: int = 8,
    usage_signals: tuple[MemoryUsageSignal, ...] = (),
) -> MemoryRetrievalRequest:
    return MemoryRetrievalRequest(
        request_id="retrieval-1",
        project_id="project-1",
        memory_id="memory-1",
        caller="supervisor-1",
        requested_at=REQUESTED_AT,
        usage_signals=usage_signals,
        limit=limit,
        domains=(MemoryDomain.HARDWARE,),
    )


def _verified_port(
    *records,
    history_pages: tuple[EngineeringMemoryHistoryPage, ...] | None = None,
) -> _MemoryPort:
    selected = (_verification_record(),) if not records else records
    snapshot = _snapshot(*tuple(_snapshot_record(item) for item in selected))
    pages = (
        (_history_page(*selected),)
        if history_pages is None
        else history_pages
    )
    return _MemoryPort(snapshot=snapshot, history_pages=pages)


def test_factory_creates_narrow_synchronous_retriever() -> None:
    retriever = create_engineering_memory_retriever(memory_port=_verified_port())
    assert isinstance(retriever, EngineeringMemoryRetriever)
    assert callable(retriever.retrieve)
    assert not hasattr(retriever, "memory_port")
    assert not hasattr(retriever, "store")
    assert not hasattr(retriever, "history")
    with pytest.raises(TypeError):
        create_engineering_memory_retriever(memory_port=object())
    with pytest.raises(TypeError):
        create_engineering_memory_retriever(memory_port=_AsyncMemoryPort())


def test_retrieve_uses_memory_port_snapshot_then_revision_bound_history() -> None:
    first = _verification_record(record_id="record-1")
    second = _verification_record(record_id="record-2")
    first_page = _history_page(
        first,
        next_cursor="revision:2:offset:1",
    )
    second_page = _history_page(second)
    port = _verified_port(
        first,
        second,
        history_pages=(first_page, second_page),
    )

    context = create_engineering_memory_retriever(memory_port=port).retrieve(
        _request()
    )

    assert tuple(type(item) for item in port.calls) == (
        GetVerifiedSnapshotRequest,
        GetHistoryRequest,
        GetHistoryRequest,
    )
    assert port.calls[1].cursor is None
    assert port.calls[2].cursor == "revision:2:offset:1"
    assert tuple(item.record_id for item in context.records) == (
        "record-1",
        "record-2",
    )


def test_verified_snapshot_projects_to_immutable_context_without_store_access() -> None:
    port = _verified_port()
    request = _request()
    before = request.model_dump_json()

    context = create_engineering_memory_retriever(memory_port=port).retrieve(request)

    assert request.model_dump_json() == before
    assert context.request_id == request.request_id
    assert context.project_id == request.project_id
    assert context.memory_id == request.memory_id
    assert context.aggregate_revision == 2
    assert tuple(item.record_id for item in context.records) == ("record-1",)
    assert tuple(item.record_id for item in context.evidence) == ("record-1",)
    assert context.confidence == 1.0
    with pytest.raises(ValidationError):
        context.confidence = 0.0


def test_retrieval_preserves_snapshot_order_and_applies_limit_without_ranking() -> None:
    second = _verification_record(record_id="record-2")
    first = _verification_record(record_id="record-1")
    port = _verified_port(second, first)

    context = create_engineering_memory_retriever(memory_port=port).retrieve(
        _request(limit=1)
    )

    assert tuple(item.record_id for item in context.records) == ("record-2",)
    assert tuple(item.record_id for item in context.evidence) == ("record-2",)


def test_child_request_ids_are_stable_unique_and_do_not_replace_parent_binding() -> None:
    request = _request()
    first_port = _verified_port()
    second_port = _verified_port()

    create_engineering_memory_retriever(memory_port=first_port).retrieve(request)
    create_engineering_memory_retriever(memory_port=second_port).retrieve(request)

    first_ids = tuple(item.request_id for item in first_port.calls)
    second_ids = tuple(item.request_id for item in second_port.calls)
    assert first_ids == second_ids
    assert len(first_ids) == len(set(first_ids))
    assert all(item.startswith("mr-") and len(item) == 35 for item in first_ids)
    assert request.request_id == "retrieval-1"


@pytest.mark.parametrize(
    "record",
    (
        _candidate_record(),
        _verification_record(result_status=VerificationStatus.FAIL),
        _terminal_record(MemoryStatus.REVOKED),
        _terminal_record(MemoryStatus.SUPERSEDED),
    ),
)
def test_non_verified_state_never_enters_context(record) -> None:
    port = _MemoryPort(
        snapshot=_snapshot(_snapshot_record(record)),
        history_pages=(_history_page(record),),
    )
    with pytest.raises(MemoryRetrievalUnavailable):
        create_engineering_memory_retriever(memory_port=port).retrieve(_request())


def test_permission_denial_safely_returns_empty_context() -> None:
    port = _MemoryPort(
        snapshot=object(),
        failure=MemoryPermissionDenied(),
    )
    context = create_engineering_memory_retriever(memory_port=port).retrieve(_request())
    assert context.records == ()
    assert context.evidence == ()
    assert context.aggregate_revision == 0
    assert context.confidence == 0.0


def test_invalid_request_and_unknown_usage_signal_are_rejected() -> None:
    retriever = create_engineering_memory_retriever(memory_port=_verified_port())
    request = _request()
    object.__setattr__(request, "limit", True)
    with pytest.raises(MemoryRetrievalRequestRejected):
        retriever.retrieve(request)

    unknown_usage = _request(
        usage_signals=(MemoryUsageSignal(record_id="missing", usage_count=1),)
    )
    with pytest.raises(MemoryRetrievalRequestRejected):
        retriever.retrieve(unknown_usage)


def test_malformed_projection_and_dependency_results_fail_closed() -> None:
    record = _verification_record()
    mismatched = _snapshot_record(record, logical_key="component:U2")
    malformed_projection = _MemoryPort(
        snapshot=_snapshot(mismatched),
        history_pages=(_history_page(record),),
    )
    with pytest.raises(MemoryRetrievalUnavailable):
        create_engineering_memory_retriever(
            memory_port=malformed_projection
        ).retrieve(_request())

    unexpected_result = _MemoryPort(
        snapshot=_history_page(record),
    )
    with pytest.raises(MemoryRetrievalUnavailable):
        create_engineering_memory_retriever(
            memory_port=unexpected_result
        ).retrieve(_request())


@pytest.mark.parametrize("failure", (RuntimeError("private"), TimeoutError("private")))
def test_dependency_failures_are_sanitized(failure: Exception) -> None:
    port = _MemoryPort(snapshot=object(), failure=failure)
    with pytest.raises(MemoryRetrievalUnavailable) as caught:
        create_engineering_memory_retriever(memory_port=port).retrieve(_request())
    assert str(caught.value) == "MEMORY_RETRIEVAL_UNAVAILABLE"
    assert caught.value.__cause__ is None
