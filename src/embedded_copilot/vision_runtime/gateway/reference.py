from __future__ import annotations

from dataclasses import dataclass

from embedded_copilot.multimodal.context import AttachmentBindingRepository
from embedded_copilot.multimodal.models import MultimodalInputType
from embedded_copilot.vision_runtime.contracts import (
    VisionPort,
    VisionReferenceConflict,
    VisionRequest,
    VisionResponse,
)
from embedded_copilot.vision_runtime.routing import VisionRouter


@dataclass(frozen=True, slots=True)
class ReferenceVisionPort(VisionPort):
    _attachment_repository: AttachmentBindingRepository
    _router: VisionRouter

    async def analyze(self, request: VisionRequest) -> VisionResponse:
        binding = self._attachment_repository.get(
            request.session_id,
            request.reference_id,
        )
        if binding.input.type is not MultimodalInputType.IMAGE:
            raise VisionReferenceConflict("vision reference type is invalid")
        result = await self._router.analyze(
            request,
            reference_summary=binding.input.summary,
        )
        return VisionResponse(summary=result.summary)
