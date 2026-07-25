from __future__ import annotations

from typing import Protocol

from embedded_copilot.search.models import SearchRequest, SearchResult


class SearchProvider(Protocol):
    provider_id: str

    def search(self, request: SearchRequest) -> tuple[SearchResult, ...]: ...
