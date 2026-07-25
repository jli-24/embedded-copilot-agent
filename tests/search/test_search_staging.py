from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from embedded_copilot.knowledge.github.client import FakeGitHubClient
from embedded_copilot.knowledge.github.models import GitHubRepositoryItem
from embedded_copilot.knowledge.source import KnowledgeSourceType
from embedded_copilot.search.approval import SearchApprovalService
from embedded_copilot.search.github import GitHubSearchAdapter
from embedded_copilot.search.models import (
    ApprovedSearchCandidate,
    SearchHistory,
    SearchRequest,
    SearchResult,
    SearchReviewAction,
    SearchStatus,
)


def _repository() -> GitHubRepositoryItem:
    return GitHubRepositoryItem(
        id="repo:1",
        title="ESP-IDF examples",
        repository="espressif/esp-idf",
        owner="espressif",
        summary="Official embedded examples.",
        reference_url="https://github.com/espressif/esp-idf",
        language="C",
        stars=100,
        score=0.8,
        category="repository",
        domain="firmware",
    )


def _result(identifier: str = "repo:1") -> SearchResult:
    return SearchResult(
        result_id=identifier,
        source_id=identifier,
        source_type=KnowledgeSourceType.GITHUB,
        title="ESP-IDF examples",
        summary="Official embedded examples.",
        relevance_score=0.8,
        uri_metadata={
            "uri": "https://github.com/espressif/esp-idf",
            "repository": "espressif/esp-idf",
            "owner": "espressif",
            "category": "repository",
        },
    )


@dataclass
class _IngestionPort:
    candidates: list[ApprovedSearchCandidate] = field(default_factory=list)

    def ingest(self, candidate: ApprovedSearchCandidate) -> None:
        self.candidates.append(candidate)


def test_github_adapter_requires_injected_client_and_stages_summary_only() -> None:
    client = FakeGitHubClient(repositories={"ESP32": [_repository()]})
    adapter = GitHubSearchAdapter(client)

    results = adapter.search(SearchRequest(query="ESP32"))

    assert adapter.provider_id == "github"
    assert results == (_result(),)
    assert client.calls == [("repository", "ESP32")]
    assert "content" not in SearchResult.model_fields
    with pytest.raises(TypeError):
        GitHubSearchAdapter()  # type: ignore[call-arg]


def test_search_history_is_bounded_and_starts_pending() -> None:
    history = SearchHistory(
        history_id="search:1",
        request=SearchRequest(query="ESP32", limit=2),
        results=(_result(),),
    )

    assert history.results[0].status is SearchStatus.PENDING
    with pytest.raises(ValidationError):
        SearchHistory(
            history_id="search:1",
            request=SearchRequest(query="ESP32", limit=1),
            results=(_result("repo:1"), _result("repo:2")),
        )


def test_approve_only_ingests_selected_safe_projection() -> None:
    port = _IngestionPort()
    service = SearchApprovalService(port)
    history = SearchHistory(
        history_id="search:1",
        request=SearchRequest(query="ESP32"),
        results=(_result("repo:1"), _result("repo:2")),
    )

    reviewed = service.review(
        history,
        action=SearchReviewAction.APPROVE,
        selected_result_ids=("repo:1",),
    )

    assert [item.status for item in reviewed.results] == [
        SearchStatus.APPROVED,
        SearchStatus.PENDING,
    ]
    assert port.candidates == [
        ApprovedSearchCandidate(
            source_id="repo:1",
            source_type=KnowledgeSourceType.GITHUB,
            summary="Official embedded examples.",
            uri_metadata={
                "uri": "https://github.com/espressif/esp-idf",
                "repository": "espressif/esp-idf",
                "owner": "espressif",
                "category": "repository",
            },
        )
    ]
    assert not hasattr(service, "promote")
    assert not hasattr(service, "create_artifact_evidence")


@pytest.mark.parametrize(
    ("action", "expected"),
    (
        (SearchReviewAction.REJECT, SearchStatus.REJECTED),
        (
            SearchReviewAction.REQUEST_MODIFICATION,
            SearchStatus.REVISION_REQUESTED,
        ),
    ),
)
def test_non_approval_actions_never_ingest(
    action: SearchReviewAction,
    expected: SearchStatus,
) -> None:
    port = _IngestionPort()
    history = SearchHistory(
        history_id="search:1",
        request=SearchRequest(query="ESP32"),
        results=(_result(),),
    )

    reviewed = SearchApprovalService(port).review(
        history,
        action=action,
        selected_result_ids=("repo:1",),
    )

    assert reviewed.results[0].status is expected
    assert port.candidates == []


def test_review_rejects_unknown_selection_and_repeat_transition() -> None:
    service = SearchApprovalService(_IngestionPort())
    history = SearchHistory(
        history_id="search:1",
        request=SearchRequest(query="ESP32"),
        results=(_result(),),
    )

    with pytest.raises(ValueError, match="selection is invalid"):
        service.review(
            history,
            action=SearchReviewAction.APPROVE,
            selected_result_ids=("missing",),
        )

    approved = service.review(
        history,
        action=SearchReviewAction.APPROVE,
        selected_result_ids=("repo:1",),
    )
    with pytest.raises(ValueError, match="transition is invalid"):
        service.review(
            approved,
            action=SearchReviewAction.REJECT,
            selected_result_ids=("repo:1",),
        )


@pytest.mark.parametrize(
    "forbidden_key",
    (
        "gpio",
        "component",
        "connection",
        "voltage",
        "current",
        "artifact_decision",
    ),
)
def test_search_result_rejects_engineering_fact_metadata(
    forbidden_key: str,
) -> None:
    payload = _result().model_dump(mode="python")
    payload["uri_metadata"] = {forbidden_key: "unsafe"}

    with pytest.raises(ValidationError):
        SearchResult.model_validate(payload)


@pytest.mark.parametrize(
    "unsafe_uri",
    (
        "http://github.com/espressif/esp-idf",
        "https://user:password@github.com/espressif/esp-idf",
        "https://github.com/espressif/esp-idf?token=secret",
        "file:///private/result.txt",
    ),
)
def test_search_result_rejects_unsafe_uri_metadata(unsafe_uri: str) -> None:
    payload = _result().model_dump(mode="python")
    payload["uri_metadata"] = {"uri": unsafe_uri}

    with pytest.raises(ValidationError):
        SearchResult.model_validate(payload)
