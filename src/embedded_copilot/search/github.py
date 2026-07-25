from __future__ import annotations

import copy

from embedded_copilot.knowledge.github.client import GitHubClient
from embedded_copilot.knowledge.github.models import GitHubRepositoryItem
from embedded_copilot.knowledge.source import KnowledgeSourceType
from embedded_copilot.search.models import SearchRequest, SearchResult


class SearchProviderError(RuntimeError):
    """Safe search provider failure."""


class GitHubSearchAdapter:
    provider_id = "github"

    def __init__(self, client: GitHubClient) -> None:
        self._client = client

    def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        isolated = SearchRequest.model_validate(
            copy.deepcopy(request.model_dump(mode="python"))
        )
        try:
            raw_results = self._client.search_repositories(isolated.query)
            if type(raw_results) is not list:
                raise TypeError("GitHub search result must be a list")
            projected = tuple(
                self._project(
                    GitHubRepositoryItem.model_validate(
                        copy.deepcopy(item.model_dump(mode="python"))
                    )
                )
                for item in raw_results[: isolated.limit]
                if isinstance(item, GitHubRepositoryItem)
            )
            if len(projected) != min(len(raw_results), isolated.limit):
                raise TypeError("GitHub search result is invalid")
            return projected
        except Exception:
            raise SearchProviderError("GitHub search failed") from None

    @staticmethod
    def _project(item: GitHubRepositoryItem) -> SearchResult:
        return SearchResult(
            result_id=item.id,
            source_id=item.id,
            source_type=KnowledgeSourceType.GITHUB,
            title=item.title,
            summary=" ".join(item.summary.split())[:512],
            relevance_score=item.score,
            uri_metadata={
                "uri": item.reference_url,
                "repository": item.repository,
                "owner": item.owner,
                "category": item.category,
            },
        )
