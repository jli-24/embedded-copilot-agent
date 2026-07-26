from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from time import monotonic
from typing import Any

import httpx

from embedded_copilot.vision_runtime.contracts import VisionRequest
from embedded_copilot.vision_runtime.providers.base import (
    ProviderVisionResponse,
    VisionCapability,
    VisionProviderTimeout,
    VisionProviderUnavailable,
)

_UNAVAILABLE_MESSAGE = "vision provider is unavailable"
_TIMEOUT_MESSAGE = "vision provider request timed out"


@dataclass(frozen=True, slots=True)
class OllamaVisionProvider:
    """Request-scoped reference-metadata reasoning through Ollama."""

    base_url: str
    model: str
    timeout_seconds: float
    transport: httpx.AsyncBaseTransport | None = None

    provider_id = "ollama"
    supported_capabilities = (VisionCapability.VISION,)

    async def analyze(
        self,
        request: VisionRequest,
        *,
        reference_summary: str,
    ) -> ProviderVisionResponse:
        prompt = (
            f"Instruction: {request.instruction_summary}\n"
            f"Image type: {request.image_type.value}\n"
            f"Reference summary: {reference_summary}"
        )
        started = monotonic()
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url.rstrip("/"),
                timeout=self.timeout_seconds,
                transport=self.transport,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                raw_response = await client.post(
                    "/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "think": False,
                    },
                )
                raw_response.raise_for_status()
                payload = raw_response.json()
            latency_ms = (monotonic() - started) * 1000.0
            return _to_provider_response(payload, latency_ms=latency_ms)
        except httpx.TimeoutException as error:
            raise VisionProviderTimeout(_TIMEOUT_MESSAGE) from error
        except VisionProviderTimeout:
            raise
        except Exception as error:
            raise VisionProviderUnavailable(_UNAVAILABLE_MESSAGE) from error


def _to_provider_response(
    payload: Any,
    *,
    latency_ms: float,
) -> ProviderVisionResponse:
    if not isinstance(payload, Mapping):
        raise ValueError("vision provider response is invalid")
    summary = payload.get("response")
    if not isinstance(summary, str):
        raise ValueError("vision provider response is invalid")
    metadata: dict[str, str | float | bool] = {
        "cached": False,
        "latency_ms": latency_ms,
    }
    finish_reason = payload.get("done_reason")
    if finish_reason is not None:
        if not isinstance(finish_reason, str):
            raise ValueError("vision provider response is invalid")
        metadata["finish_reason"] = finish_reason
    return ProviderVisionResponse(summary=summary, metadata=metadata)
