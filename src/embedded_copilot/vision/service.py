from __future__ import annotations

import copy

from embedded_copilot.intelligence._validation import safe_identifier, safe_text
from embedded_copilot.multimodal.context import AttachmentBindingRepository
from embedded_copilot.multimodal.models import MultimodalInputType
from embedded_copilot.vision.adapter import VisionAdapter
from embedded_copilot.vision.models import VisionSuggestion


class VisionService:
    def __init__(
        self,
        *,
        repository: AttachmentBindingRepository,
        adapter: VisionAdapter,
    ) -> None:
        self._repository = repository
        self._adapter = adapter

    async def analyze(
        self,
        *,
        session_id: str,
        reference_id: str,
        message_summary: str,
    ) -> VisionSuggestion:
        session = safe_identifier(session_id, field="session_id")
        reference = safe_identifier(reference_id, field="reference_id")
        message = safe_text(
            message_summary,
            field="message_summary",
            max_length=512,
        )
        binding = self._repository.get(session, reference)
        if binding.input.type is not MultimodalInputType.IMAGE:
            raise ValueError("vision requires an image reference")
        raw = await self._adapter.analyze(binding.input, message)
        suggestion = VisionSuggestion.model_validate(
            copy.deepcopy(raw.model_dump(mode="python"))
        )
        if suggestion.source_reference.casefold() != reference.casefold():
            raise ValueError("vision source reference is inconsistent")
        return suggestion
