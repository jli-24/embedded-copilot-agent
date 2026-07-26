from __future__ import annotations

import copy
from typing import Protocol

from embedded_copilot.datasheet.intelligence.models import DatasheetSuggestion
from embedded_copilot.datasheet.models import UnifiedDatasheetModel
from embedded_copilot.multimodal.context import AttachmentBinding
from embedded_copilot.multimodal.models import MultimodalInputType


class DatasheetIntelligenceError(RuntimeError):
    """Safe failure raised by the suggestion-only Datasheet boundary."""


class DatasheetSuggestionParser(Protocol):
    def parse(self, binding: AttachmentBinding) -> UnifiedDatasheetModel: ...


class DatasheetIntelligenceService:
    def __init__(self, *, parser: DatasheetSuggestionParser) -> None:
        self._parser = parser

    def analyze(self, binding: AttachmentBinding) -> DatasheetSuggestion:
        snapshot = AttachmentBinding.model_validate(
            copy.deepcopy(binding.model_dump(mode="python"))
        )
        if snapshot.input.type is not MultimodalInputType.FILE:
            raise ValueError("datasheet intelligence requires a file reference")
        try:
            raw = self._parser.parse(snapshot)
            parsed = UnifiedDatasheetModel.model_validate(
                copy.deepcopy(raw.model_dump(mode="python"))
            )
            suggestion = DatasheetSuggestion(
                source_reference=snapshot.input.reference_id,
                chip=(
                    f"{parsed.component.manufacturer} "
                    f"{parsed.component.part_number}"
                ),
                interface=tuple(
                    f"{item.name} ({item.protocol})" for item in parsed.interfaces
                ),
                pin_reference=tuple(
                    f"{item.number} {item.name}" for item in parsed.pins
                ),
                electrical_reference=tuple(
                    f"{item.parameter} ({item.unit})"
                    for item in parsed.electrical_specs
                ),
            )
        except Exception:
            raise DatasheetIntelligenceError("datasheet parser failed") from None
        return DatasheetSuggestion.model_validate(
            copy.deepcopy(suggestion.model_dump(mode="python"))
        )
