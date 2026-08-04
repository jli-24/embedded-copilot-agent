from __future__ import annotations

import copy
from pydantic import ValidationError

from .contracts import (
    ModelRequest,
    ModelResponse,
    ModelRuntimePort,
    validate_model_response,
)
from .exceptions import ModelRequestRejected
from .contracts import validate_model_request


class ModelRuntimeService:
    __slots__ = ("_port",)

    def __init__(self, port: ModelRuntimePort) -> None:
        if not isinstance(port, ModelRuntimePort):
            raise TypeError("model runtime port is invalid")
        self._port = port

    def generate(self, request: ModelRequest) -> ModelResponse:
        try:
            checked = validate_model_request(request)
            result = self._port.generate(copy.deepcopy(checked))
            return validate_model_response(result)
        except ModelRequestRejected:
            raise
        except (TypeError, ValueError, ValidationError) as error:
            raise ModelRequestRejected() from error


ModelService = ModelRuntimeService
