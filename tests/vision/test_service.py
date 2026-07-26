from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from embedded_copilot.core.config import Settings
from embedded_copilot.multimodal.context import (
    AttachmentBinding,
    AttachmentBindingNotFound,
    ProcessLocalAttachmentBindingRepository,
)
from embedded_copilot.multimodal.models import (
    MultimodalInput,
    MultimodalInputType,
)
from embedded_copilot.vision_runtime import (
    ImageType,
    VisionRequest,
    VisionRuntime,
    create_vision_runtime,
)
from embedded_copilot.vision_runtime.gateway import VisionReferenceConflict
from embedded_copilot.vision_runtime.providers import VisionProviderUnavailable

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


def _request(session_id: str = "session:1") -> VisionRequest:
    return VisionRequest(
        session_id=session_id,
        reference_id="reference:1",
        image_type=ImageType.UNKNOWN,
        instruction_summary="Review the referenced metadata.",
    )


def test_factory_composes_reference_bound_vision_port_without_leaking_internals() -> (
    None
):
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": "The reference metadata requires engineer review.",
                "done_reason": "stop",
            },
        )

    runtime = create_vision_runtime(
        Settings(
            _env_file=None,
            vision_provider="ollama",
            ollama_vision_model="deployment-selected-model",
        ),
        _repository(),
        transport=httpx.MockTransport(respond),
    )

    response = asyncio.run(runtime.vision_port().analyze(_request()))

    assert isinstance(runtime, VisionRuntime)
    assert response.model_dump(mode="json") == {
        "output_type": "reasoning_suggestion",
        "summary": "The reference metadata requires engineer review.",
        "review_required": True,
    }
    for forbidden in (
        "provider",
        "router",
        "registry",
        "repository",
        "configuration",
        "settings",
        "config",
        "health",
    ):
        assert not hasattr(runtime, forbidden)
        assert not hasattr(runtime.vision_port(), forbidden)


def test_vision_port_rejects_cross_session_reference_access() -> None:
    runtime = create_vision_runtime(
        Settings(_env_file=None),
        _repository(),
    )

    with pytest.raises(AttachmentBindingNotFound):
        asyncio.run(runtime.vision_port().analyze(_request("session:2")))


def test_vision_port_rejects_non_image_reference_before_provider_selection() -> None:
    runtime = create_vision_runtime(
        Settings(_env_file=None),
        _repository(MultimodalInputType.FILE),
    )

    with pytest.raises(
        VisionReferenceConflict,
        match=r"^vision reference type is invalid$",
    ):
        asyncio.run(runtime.vision_port().analyze(_request()))


def test_default_runtime_reports_provider_unavailable_after_reference_resolution() -> (
    None
):
    runtime = create_vision_runtime(
        Settings(_env_file=None),
        _repository(),
    )

    with pytest.raises(
        VisionProviderUnavailable,
        match=r"^vision provider is unavailable$",
    ):
        asyncio.run(runtime.vision_port().analyze(_request()))
