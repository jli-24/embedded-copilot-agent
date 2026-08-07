from __future__ import annotations

from typing import Protocol

from ..contracts import EngineeringCompletionPort, EngineeringCompletionSnapshot


class _SnapshotSource(Protocol):
    def get_snapshot(self, project_id: str) -> EngineeringCompletionSnapshot | None: ...


class ProjectionEngineeringCompletionPort(EngineeringCompletionPort):
    def __init__(self, source: _SnapshotSource) -> None:
        if not callable(getattr(source, "get_snapshot", None)):
            raise TypeError("completion projection source is invalid")
        self._source = source

    def get_snapshot(self, project_id: str) -> EngineeringCompletionSnapshot | None:
        return self._source.get_snapshot(project_id)


__all__ = ["ProjectionEngineeringCompletionPort"]
