from __future__ import annotations

from collections.abc import Mapping, Sequence

from embedded_copilot.knowledge.models import KnowledgeResult, KnowledgeSource
from embedded_copilot.knowledge.providers import _OfflineFixtureProvider


class GitHubSearchProvider(_OfflineFixtureProvider):
    """Offline-only GitHub provider backed by explicit query fixtures."""

    def __init__(
        self,
        responses: Mapping[str, Sequence[KnowledgeResult]] | None = None,
    ) -> None:
        super().__init__(
            responses,
            provider_name="github",
            source=KnowledgeSource.GITHUB,
        )
