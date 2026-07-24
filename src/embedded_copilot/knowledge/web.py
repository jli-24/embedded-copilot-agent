from __future__ import annotations

from collections.abc import Mapping, Sequence

from embedded_copilot.knowledge.models import KnowledgeResult, KnowledgeSource
from embedded_copilot.knowledge.providers._fixtures import _OfflineFixtureProvider


class WebSearchProvider(_OfflineFixtureProvider):
    """Offline-only Web provider backed by explicit query fixtures."""

    def __init__(
        self,
        responses: Mapping[str, Sequence[KnowledgeResult]] | None = None,
    ) -> None:
        super().__init__(
            responses,
            provider_name="web",
            source=KnowledgeSource.WEB,
        )
