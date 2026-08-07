from __future__ import annotations

from .contracts import EngineeringReasoningPort, VisionModelPort
from .service import MultimodalInputService


def create_multimodal_input_service(
    vision: VisionModelPort,
    reasoning: EngineeringReasoningPort | None = None,
) -> MultimodalInputService:
    return MultimodalInputService(vision, reasoning)


__all__ = ["create_multimodal_input_service"]
