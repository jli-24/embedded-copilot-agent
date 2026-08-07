from __future__ import annotations

import inspect

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from embedded_copilot.multimodal_input.contracts import (
    InputType,
    MultimodalAnalysisProjection,
    VisionRequest,
    validate_projection,
)
from embedded_copilot.multimodal_input.exceptions import (
    MultimodalRejected,
    MultimodalUnavailable,
)
from embedded_copilot.multimodal_input.models import fingerprint, identifier
from embedded_copilot.multimodal_input.service import MultimodalInputService

router = APIRouter()


class MultimodalAnalyzeBody(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )

    project_id: str
    source_reference: str
    input_type: str
    context_fingerprint: str

    @field_validator("project_id", "source_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("context_fingerprint", mode="before")
    @classmethod
    def validate_context(cls, value: object) -> str:
        return fingerprint(value, field="context_fingerprint")


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


async def _call(value):
    return await value if inspect.isawaitable(value) else value


@router.post(
    "/api/multimodal/v29/analyze",
    response_model=MultimodalAnalysisProjection,
)
async def analyze_multimodal(
    body: MultimodalAnalyzeBody, request: Request
) -> MultimodalAnalysisProjection | JSONResponse:
    try:
        checked_body = MultimodalAnalyzeBody.model_validate(
            body.model_dump(mode="python")
        )
        vision_request = VisionRequest.create(
            project_id=checked_body.project_id,
            source_reference=checked_body.source_reference,
            input_type=InputType(checked_body.input_type),
            context_fingerprint=checked_body.context_fingerprint,
        )
    except (ValidationError, TypeError, ValueError):
        return _error("QUERY_REJECTED", 422)
    vision = getattr(request.app.state, "multimodal_vision_port", None)
    reasoning = getattr(request.app.state, "multimodal_reasoning_port", None)
    if vision is None or not callable(getattr(vision, "analyze", None)):
        return _error("MULTIMODAL_UNAVAILABLE", 503)
    try:
        service = MultimodalInputService(vision, reasoning)
        result = await _call(service.analyze(vision_request))
        return validate_projection(result)
    except MultimodalUnavailable:
        return _error("MULTIMODAL_UNAVAILABLE", 503)
    except MultimodalRejected:
        return _error("QUERY_REJECTED", 422)
    except (ValidationError, TypeError, ValueError):
        return _error("QUERY_REJECTED", 422)
    except Exception:  # noqa: BLE001 - adapter details are intentionally sanitized
        return _error("MULTIMODAL_UNAVAILABLE", 503)


__all__ = ["MultimodalAnalyzeBody", "router"]
