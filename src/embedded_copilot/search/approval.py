from __future__ import annotations

import copy
from typing import Protocol

from embedded_copilot.search.models import (
    ApprovedSearchCandidate,
    SearchHistory,
    SearchResult,
    SearchReviewAction,
    SearchStatus,
)


class KnowledgeIngestionPort(Protocol):
    def ingest(self, candidate: ApprovedSearchCandidate) -> None: ...


class SearchIngestionError(RuntimeError):
    """Safe approved-ingestion failure."""


class SearchApprovalService:
    def __init__(self, ingestion: KnowledgeIngestionPort) -> None:
        self._ingestion = ingestion

    def review(
        self,
        history: SearchHistory,
        *,
        action: SearchReviewAction,
        selected_result_ids: tuple[str, ...],
    ) -> SearchHistory:
        isolated = SearchHistory.model_validate(
            copy.deepcopy(history.model_dump(mode="python"))
        )
        selected = tuple(selected_result_ids)
        if not selected or len({item.casefold() for item in selected}) != len(selected):
            raise ValueError("search selection is invalid")
        selected_keys = {item.casefold() for item in selected}
        by_id = {item.result_id.casefold(): item for item in isolated.results}
        if not selected_keys.issubset(by_id):
            raise ValueError("search selection is invalid")
        if any(by_id[key].status is not SearchStatus.PENDING for key in selected_keys):
            raise ValueError("search transition is invalid")

        if action is SearchReviewAction.APPROVE:
            try:
                for item in isolated.results:
                    if item.result_id.casefold() in selected_keys:
                        self._ingestion.ingest(
                            ApprovedSearchCandidate(
                                source_id=item.source_id,
                                source_type=item.source_type,
                                summary=item.summary,
                                uri_metadata=item.uri_metadata,
                            )
                        )
            except Exception:
                raise SearchIngestionError("approved search ingestion failed") from None

        status = {
            SearchReviewAction.APPROVE: SearchStatus.APPROVED,
            SearchReviewAction.REJECT: SearchStatus.REJECTED,
            SearchReviewAction.REQUEST_MODIFICATION: SearchStatus.REVISION_REQUESTED,
        }[action]
        reviewed = tuple(
            (
                self._with_status(item, status)
                if item.result_id.casefold() in selected_keys
                else item
            )
            for item in isolated.results
        )
        return SearchHistory(
            history_id=isolated.history_id,
            request=isolated.request,
            results=reviewed,
        )

    @staticmethod
    def _with_status(result: SearchResult, status: SearchStatus) -> SearchResult:
        payload = result.model_dump(mode="python")
        payload["status"] = status
        return SearchResult.model_validate(payload)
