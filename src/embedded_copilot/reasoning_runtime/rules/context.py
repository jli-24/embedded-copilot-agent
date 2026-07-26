from __future__ import annotations

from dataclasses import dataclass

from embedded_copilot.context_runtime.contracts import (
    DatasheetContext,
    FileContext,
    VisionContext,
)
from embedded_copilot.reasoning_runtime.contracts import SourceType


@dataclass(frozen=True, slots=True)
class RuleContext:
    reference_ids: tuple[str, ...]
    source_types: tuple[SourceType, ...]
    datasheet_candidates: tuple[DatasheetContext, ...]
    file_summaries: tuple[FileContext, ...]
    vision_refs: tuple[VisionContext, ...]

    def source_type_for(self, reference_id: str) -> SourceType:
        key = reference_id.casefold()
        for candidate, source_type in zip(
            self.reference_ids,
            self.source_types,
            strict=True,
        ):
            if candidate.casefold() == key:
                return source_type
        raise ValueError("rule reference is outside the snapshot")
