from __future__ import annotations

import copy
import re
from collections.abc import Callable

from embedded_copilot.knowledge.exceptions import (
    GitHubRateLimitError,
    ProviderError,
    ProviderInvalidResult,
    ProviderUnavailable,
)
from embedded_copilot.knowledge.github.client import GitHubClient
from embedded_copilot.knowledge.github.models import (
    GitHubCodeItem,
    GitHubIssueItem,
    GitHubReleaseItem,
    GitHubRepositoryItem,
)
from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.schemas.result import ContractModel


_TYPE_ORDER = ("repository", "code", "issue", "release")
_TYPE_SET = frozenset(_TYPE_ORDER)
_DOMAIN_TYPES = {
    "debug": "issue",
    "firmware": "code",
    "hardware": "repository",
    "pcb": "repository",
}
_RELEASE_MARKERS = ("release", "version", "changelog")
_ISSUE_MARKERS = (
    "issue",
    "bug",
    "error",
    "failure",
    "crash",
    "hard fault",
    "compile error",
)
_CODE_MARKERS = ("example", "sample", "code", "driver")
_REFERENCE_URL = re.compile(
    r"^https://github\.com/"
    r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
    r"(?:/issues/[1-9][0-9]*|/releases/[A-Za-z0-9_.-]+)?$"
)
_CREDENTIAL_MARKER = re.compile(
    r"(?:bearer\s+[A-Za-z0-9._-]+|ghp_[A-Za-z0-9]+|"
    r"github_pat_[A-Za-z0-9_]+|(?:token|secret|password)\s*[=:])",
    re.IGNORECASE,
)
_MAX_CONTENT_CHARS = 2000


GitHubRawItem = (
    GitHubRepositoryItem
    | GitHubCodeItem
    | GitHubIssueItem
    | GitHubReleaseItem
)


class GitHubKnowledgeProvider:
    """Convert candidates from an explicitly injected GitHub client."""

    provider_name = "github"
    supported_sources = (KnowledgeSource.GITHUB,)

    def __init__(self, client: GitHubClient | None = None) -> None:
        if client is not None and not isinstance(client, GitHubClient):
            raise ProviderInvalidResult("GitHub provider configuration is invalid")
        self._client = client

    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        if self._client is None:
            return []
        isolated, selected = _isolate_query(query)

        calls: dict[str, Callable[[str], object]] = {
            "repository": self._client.search_repositories,
            "code": self._client.search_code,
            "issue": self._client.search_issues,
            "release": self._client.get_release,
        }
        results: list[KnowledgeResult] = []
        for document_type in selected:
            raw_results = _call_client(calls[document_type], isolated.query)
            try:
                results.extend(_map_results(raw_results, document_type))
            except ProviderError:
                raise
            except Exception:
                raise ProviderInvalidResult(
                    "GitHub provider result is invalid"
                ) from None
        return results


def _isolate_query(
    query: KnowledgeQuery,
) -> tuple[KnowledgeQuery, tuple[str, ...]]:
    isolated: KnowledgeQuery | None = None
    selected: tuple[str, ...] = ()
    invalid = False
    try:
        isolated = KnowledgeQuery.model_validate(
            copy.deepcopy(query.model_dump(mode="python"))
        )
        selected = _select_types(isolated)
    except Exception:
        invalid = True
    if invalid or isolated is None:
        raise ProviderInvalidResult("GitHub provider query is invalid")
    return isolated, selected


def _call_client(
    call: Callable[[str], object],
    query: str,
) -> object:
    raw_results: object = None
    failure: ProviderError | None = None
    try:
        raw_results = call(query)
    except GitHubRateLimitError:
        failure = GitHubRateLimitError("GitHub rate limit exceeded")
    except ProviderInvalidResult:
        failure = ProviderInvalidResult("GitHub provider result is invalid")
    except ProviderError:
        failure = ProviderUnavailable("GitHub provider is unavailable")
    except Exception:
        failure = ProviderUnavailable("GitHub provider is unavailable")
    if failure is not None:
        raise failure
    return raw_results


def _select_types(query: KnowledgeQuery) -> tuple[str, ...]:
    explicit = query.metadata.get("github_types")
    if explicit is not None:
        if not isinstance(explicit, list) or not explicit:
            raise ValueError("GitHub types are invalid")
        normalized: list[str] = []
        for value in explicit:
            if not isinstance(value, str) or value.strip().casefold() not in _TYPE_SET:
                raise ValueError("GitHub type is invalid")
            candidate = value.strip().casefold()
            if candidate not in normalized:
                normalized.append(candidate)
        return tuple(kind for kind in _TYPE_ORDER if kind in normalized)

    domains = query.metadata.get("domains")
    if isinstance(domains, list) and domains:
        selected = {
            _DOMAIN_TYPES[value.strip().casefold()]
            for value in domains
            if isinstance(value, str)
            and value.strip().casefold() in _DOMAIN_TYPES
        }
        if selected:
            return tuple(kind for kind in _TYPE_ORDER if kind in selected)

    normalized_query = query.query.casefold()
    if any(marker in normalized_query for marker in _RELEASE_MARKERS):
        return ("release",)
    if any(marker in normalized_query for marker in _ISSUE_MARKERS):
        return ("issue",)
    if any(marker in normalized_query for marker in _CODE_MARKERS):
        return ("code",)
    return ("repository",)


def _map_results(raw_results: object, document_type: str) -> list[KnowledgeResult]:
    expected_models: dict[str, type[ContractModel]] = {
        "repository": GitHubRepositoryItem,
        "code": GitHubCodeItem,
        "issue": GitHubIssueItem,
        "release": GitHubReleaseItem,
    }
    expected = expected_models[document_type]
    if type(raw_results) is not list:
        raise ProviderInvalidResult("GitHub provider result is invalid")
    mapped: list[KnowledgeResult] = []
    for raw_item in raw_results:
        if not isinstance(raw_item, expected):
            raise ProviderInvalidResult("GitHub provider result is invalid")
        item = expected.model_validate(
            copy.deepcopy(raw_item.model_dump(mode="python"))
        )
        mapped.append(_map_item(item, document_type))
    return mapped


def _map_item(item: ContractModel, document_type: str) -> KnowledgeResult:
    raw = item.model_dump(mode="python")
    if any(
        isinstance(value, str) and _CREDENTIAL_MARKER.search(value)
        for value in raw.values()
    ):
        raise ProviderInvalidResult("GitHub provider result is invalid")
    reference_url = raw["reference_url"]
    if not isinstance(reference_url, str) or not _REFERENCE_URL.fullmatch(
        reference_url
    ):
        raise ProviderInvalidResult("GitHub provider result is invalid")
    summary = " ".join(str(raw["summary"]).split())[:_MAX_CONTENT_CHARS]
    if not summary:
        raise ProviderInvalidResult("GitHub provider result is invalid")
    metadata: dict[str, object] = {
        "repository": raw["repository"],
        "owner": raw["owner"],
        "document_type": document_type,
        "reference_url": reference_url,
        "category": raw["category"],
        "domain": raw["domain"],
    }
    language = raw.get("language")
    if language is not None:
        metadata["language"] = language
    stars = raw.get("stars")
    if stars is not None:
        metadata["stars"] = stars
    return KnowledgeResult(
        id=f"github:{document_type}:{raw['id']}",
        title=str(raw["title"]),
        content=summary,
        source=KnowledgeSource.GITHUB,
        score=raw["score"],
        metadata=metadata,
    )
