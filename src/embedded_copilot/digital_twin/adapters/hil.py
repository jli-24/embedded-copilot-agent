from __future__ import annotations

from typing import Protocol

from ..contracts import DigitalTwinPort, DigitalTwinSnapshot


class _ProjectionPort(Protocol):
    def get_snapshot(self, project_id: str) -> DigitalTwinSnapshot | None: ...


class HILDigitalTwinAdapter(DigitalTwinPort):
    def __init__(self, source: _ProjectionPort) -> None:
        self._source = source

    def get_snapshot(self, project_id: str) -> DigitalTwinSnapshot | None:
        return self._source.get_snapshot(project_id)


__all__ = ["HILDigitalTwinAdapter"]
