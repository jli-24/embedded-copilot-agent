from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from time import monotonic
from typing import Any

import httpx

from embedded_copilot.intelligence.exceptions import ModelProviderUnavailable
from embedded_copilot.intelligence.models import (
    ModelCapability,
    ModelInput,
    ModelResponse,
)
from embedded_copilot.schemas.model import ModelRequest

_UNAVAILABLE_MESSAGE = "model provider is unavailable"


@dataclass(frozen=True, slots=True)
class OllamaProvider:
    base_url: str
    model: str
    timeout_seconds: float
    transport: httpx.AsyncBaseTransport | None = None

    provider_id = "ollama"
    supported_tasks = (
        ModelCapability.CHAT,
        ModelCapability.CODE,
        ModelCapability.REASONING,
    )

    async def generate(
        self,
        request: ModelRequest,
        model_input: ModelInput,
    ) -> ModelResponse:
        try:
            capability = ModelCapability(request.task_type.value)
            if capability not in self.supported_tasks:
                raise ModelProviderUnavailable(_UNAVAILABLE_MESSAGE)
            prompt = "\n\n".join(
                (model_input.message_summary, *model_input.context_summaries)
            )
            started = monotonic()
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
            return _to_model_response(payload, latency_ms=latency_ms)
        except ModelProviderUnavailable:
            raise
        except Exception as error:
            raise ModelProviderUnavailable(_UNAVAILABLE_MESSAGE) from error


def _to_model_response(payload: Any, *, latency_ms: float) -> ModelResponse:
    if not isinstance(payload, Mapping):
        raise ValueError("model response is invalid")
    text = payload.get("response")
    if not isinstance(text, str):
        raise ValueError("model response is invalid")
    metadata: dict[str, str | float | bool] = {
        "cached": False,
        "latency_ms": latency_ms,
    }
    finish_reason = payload.get("done_reason")
    if finish_reason is not None:
        if not isinstance(finish_reason, str):
            raise ValueError("model response is invalid")
        metadata["finish_reason"] = finish_reason
    return ModelResponse(
        text=text,
        metadata=metadata,
        source=OllamaProvider.provider_id,
    )
