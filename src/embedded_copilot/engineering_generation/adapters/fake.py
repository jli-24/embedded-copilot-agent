from __future__ import annotations

import copy

from ..contracts import GenerationSnapshot


class FakeGenerationPort:
    __slots__ = ("_snapshot",)

    def __init__(self, snapshot: GenerationSnapshot | None = None) -> None:
        self._snapshot = snapshot

    def get_snapshot(self, project_id: str) -> GenerationSnapshot | None:
        if self._snapshot is None or self._snapshot.project_id != project_id:
            return None
        return GenerationSnapshot.model_validate(copy.deepcopy(self._snapshot))
