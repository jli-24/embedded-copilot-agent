from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.model_runtime.contracts import (
    ModelRequest,
    ModelResponse,
    ModelRuntimePort,
    validate_model_response,
)
from embedded_copilot.model_runtime.exceptions import ModelRuntimeUnavailable


@runtime_checkable
class ModelTransport(Protocol):
    def generate(self, request: ModelRequest) -> ModelResponse: ...


class OpenAICompatibleModelAdapter(ModelRuntimePort):
    def __init__(self, transport: ModelTransport | None = None) -> None:
        self._transport = transport

    def generate(self, request: ModelRequest) -> ModelResponse:
        if self._transport is None:
            raise ModelRuntimeUnavailable()
        try:
            return validate_model_response(self._transport.generate(request))
        except ModelRuntimeUnavailable:
            raise
        except Exception as error:
            raise ModelRuntimeUnavailable() from error


__all__ = ["ModelTransport", "OpenAICompatibleModelAdapter"]
