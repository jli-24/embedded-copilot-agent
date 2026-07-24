from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Protocol, TypeVar, runtime_checkable

from embedded_copilot.knowledge.exceptions import ProviderInvalidResult
from embedded_copilot.knowledge.github.models import (
    GitHubCodeItem,
    GitHubIssueItem,
    GitHubReleaseItem,
    GitHubRepositoryItem,
)
from embedded_copilot.schemas.result import ContractModel


@runtime_checkable
class GitHubClient(Protocol):
    def search_repositories(self, query: str) -> list[GitHubRepositoryItem]: ...

    def search_code(self, query: str) -> list[GitHubCodeItem]: ...

    def search_issues(self, query: str) -> list[GitHubIssueItem]: ...

    def get_release(self, query: str) -> list[GitHubReleaseItem]: ...


RawItemT = TypeVar("RawItemT", bound=ContractModel)


class FakeGitHubClient:
    """Exact-query synthetic GitHub client with no external side effects."""

    def __init__(
        self,
        *,
        repositories: Mapping[str, Sequence[GitHubRepositoryItem]] | None = None,
        code: Mapping[str, Sequence[GitHubCodeItem]] | None = None,
        issues: Mapping[str, Sequence[GitHubIssueItem]] | None = None,
        releases: Mapping[str, Sequence[GitHubReleaseItem]] | None = None,
    ) -> None:
        self._repositories = _copy_fixtures(
            repositories,
            GitHubRepositoryItem,
        )
        self._code = _copy_fixtures(code, GitHubCodeItem)
        self._issues = _copy_fixtures(issues, GitHubIssueItem)
        self._releases = _copy_fixtures(releases, GitHubReleaseItem)
        self.calls: list[tuple[str, str]] = []

    def search_repositories(self, query: str) -> list[GitHubRepositoryItem]:
        self.calls.append(("repository", query))
        return _copy_results(self._repositories.get(query, ()), GitHubRepositoryItem)

    def search_code(self, query: str) -> list[GitHubCodeItem]:
        self.calls.append(("code", query))
        return _copy_results(self._code.get(query, ()), GitHubCodeItem)

    def search_issues(self, query: str) -> list[GitHubIssueItem]:
        self.calls.append(("issue", query))
        return _copy_results(self._issues.get(query, ()), GitHubIssueItem)

    def get_release(self, query: str) -> list[GitHubReleaseItem]:
        self.calls.append(("release", query))
        return _copy_results(self._releases.get(query, ()), GitHubReleaseItem)


def _copy_fixtures(
    fixtures: Mapping[str, Sequence[RawItemT]] | None,
    model: type[RawItemT],
) -> dict[str, tuple[RawItemT, ...]]:
    copied: dict[str, tuple[RawItemT, ...]] = {}
    invalid = False
    try:
        for raw_query, values in (fixtures or {}).items():
            if (
                not isinstance(raw_query, str)
                or not raw_query
                or raw_query != raw_query.strip()
                or raw_query in copied
            ):
                raise ValueError("GitHub fixture query is invalid")
            copied[raw_query] = tuple(_copy_results(values, model))
    except Exception:
        invalid = True
    if invalid:
        raise ProviderInvalidResult("GitHub client fixture is invalid")
    return copied


def _copy_results(
    values: Sequence[RawItemT],
    model: type[RawItemT],
) -> list[RawItemT]:
    results: list[RawItemT] = []
    for value in values:
        if not isinstance(value, model):
            raise TypeError("GitHub fixture item is invalid")
        results.append(
            model.model_validate(copy.deepcopy(value.model_dump(mode="python")))
        )
    return results
