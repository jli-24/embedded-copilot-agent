from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from embedded_copilot.intelligence.gateway import ModelGateway
from embedded_copilot.intelligence.providers.mock import DeterministicMockProvider
from embedded_copilot.multimodal.context import (
    AttachmentBinding,
    ProcessLocalAttachmentBindingRepository,
)
from embedded_copilot.multimodal.models import (
    MultimodalInput,
    MultimodalInputType,
)
from embedded_copilot.vision.adapter import GatewayVisionAdapter
from embedded_copilot.vision.models import VisionSuggestion
from embedded_copilot.vision.service import VisionService

CREATED = datetime(2026, 7, 26, 9, 0, tzinfo=timezone.utc)


def _repository(
    input_type: MultimodalInputType = MultimodalInputType.IMAGE,
) -> ProcessLocalAttachmentBindingRepository:
    repository = ProcessLocalAttachmentBindingRepository()
    repository.bind(
        AttachmentBinding(
            session_id="session:1",
            input=MultimodalInput(
                type=input_type,
                reference_id="reference:1",
                summary="Referenced engineering image metadata.",
            ),
            basename="reference.png",
            size_bytes=1024,
            created_at=CREATED,
        )
    )
    return repository


def test_vision_service_returns_source_bound_reasoning_suggestion() -> None:
    provider = DeterministicMockProvider(
        response_text="The image may contain an MCU region; confirm during review."
    )
    service = VisionService(
        repository=_repository(),
        adapter=GatewayVisionAdapter(ModelGateway((provider,))),
    )

    suggestion = asyncio.run(
        service.analyze(
            session_id="session:1",
            reference_id="reference:1",
            message_summary="Review the referenced schematic image.",
        )
    )

    assert suggestion.output_type == "reasoning_suggestion"
    assert suggestion.source_reference == "reference:1"
    assert suggestion.confidence == 0.0
    assert "confirm" in suggestion.summary


def test_vision_service_rejects_non_image_reference() -> None:
    service = VisionService(
        repository=_repository(MultimodalInputType.FILE),
        adapter=GatewayVisionAdapter(ModelGateway((DeterministicMockProvider(),))),
    )

    with pytest.raises(ValueError, match="image reference"):
        asyncio.run(
            service.analyze(
                session_id="session:1",
                reference_id="reference:1",
                message_summary="Review the reference.",
            )
        )


def test_vision_suggestion_rejects_engineering_fact_fields() -> None:
    with pytest.raises(ValidationError):
        VisionSuggestion.model_validate(
            {
                "summary": "This remains a suggestion.",
                "confidence": 0.2,
                "source_reference": "reference:1",
                "gpio": "GPIO4",
            }
        )
