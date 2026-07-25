"""Approval-gated, process-local search staging."""

from embedded_copilot.search.approval import (
    KnowledgeIngestionPort,
    SearchApprovalService,
)
from embedded_copilot.search.models import (
    ApprovedSearchCandidate,
    SearchHistory,
    SearchRequest,
    SearchResult,
    SearchReviewAction,
    SearchStatus,
)
from embedded_copilot.search.provider import SearchProvider

__all__ = [
    "ApprovedSearchCandidate",
    "KnowledgeIngestionPort",
    "SearchApprovalService",
    "SearchHistory",
    "SearchProvider",
    "SearchRequest",
    "SearchResult",
    "SearchReviewAction",
    "SearchStatus",
]
