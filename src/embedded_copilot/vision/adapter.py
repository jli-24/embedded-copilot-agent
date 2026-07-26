from __future__ import annotations

from typing import Protocol

from embedded_copilot.intelligence.gateway import ModelGateway
from embedded_copilot.intelligence.models import ModelInput
from embedded_copilot.multimodal.models import MultimodalInput
from embedded_copilot.schemas.model import (
    ModelInputType,
    ModelRequest,
    ModelTaskType,
)
from embedded_copilot.vision.models import VisionSuggestion


class VisionAdapter(Protocol):
    async def analyze(
        self,
        input: MultimodalInput,
        message_summary: str,
    ) -> VisionSuggestion: ...


class GatewayVisionAdapter:
    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway

    async def analyze(
        self,
        input: MultimodalInput,
        message_summary: str,
    ) -> VisionSuggestion:
        response = await self._gateway.generate(
            ModelRequest(
                task_type=ModelTaskType.VISION,
                input_type=ModelInputType.IMAGE,
                context_ids=(input.reference_id,),
            ),
            ModelInput(
                message_summary=message_summary,
                context_summaries=(input.summary,),
            ),
        )
        return VisionSuggestion(
            summary=response.text,
            confidence=0.0,
            source_reference=input.reference_id,
        )
