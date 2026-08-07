from __future__ import annotations

from embedded_copilot.engineering_context import (
    EngineeringContextQuery,
    EngineeringContextService,
)


class _EmptyMemory:
    def list_approved(self, project_id: str):
        return ()


class _EmptyGraph:
    def project(self, project_id: str):
        return None


def test_retrieval_returns_none_without_approved_or_verified_projection() -> None:
    service = EngineeringContextService(
        memory_port=_EmptyMemory(), graph_port=_EmptyGraph()
    )
    assert service.get_context(
        EngineeringContextQuery(project_id="project-1", query="camera")
    ) is None
