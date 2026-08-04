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
class LocalModelRunner(Protocol):
    def generate(self, request: ModelRequest) -> ModelResponse: ...


class LocalModelAdapter(ModelRuntimePort):
    def __init__(self, runner: LocalModelRunner | None = None) -> None:
        self._runner = runner

    def generate(self, request: ModelRequest) -> ModelResponse:
        if self._runner is None:
            raise ModelRuntimeUnavailable()
        try:
            return validate_model_response(self._runner.generate(request))
        except ModelRuntimeUnavailable:
            raise
        except Exception as error:
            raise ModelRuntimeUnavailable() from error


__all__ = ["LocalModelAdapter", "LocalModelRunner"]
