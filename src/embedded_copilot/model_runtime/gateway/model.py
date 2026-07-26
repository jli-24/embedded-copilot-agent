from __future__ import annotations

import copy
from dataclasses import dataclass

from embedded_copilot.intelligence.exceptions import (
    ModelGatewayError,
    ModelProviderUnavailable,
)
from embedded_copilot.intelligence.models import ModelInput, ModelResponse
from embedded_copilot.model_runtime.routing import ModelRouter
from embedded_copilot.schemas.model import ModelRequest


@dataclass(frozen=True, slots=True)
class ModelGateway:
    _router: ModelRouter

    async def generate(
        self,
        request: ModelRequest,
        model_input: ModelInput,
    ) -> ModelResponse:
        isolated_request = ModelRequest.model_validate(
            copy.deepcopy(request.model_dump(mode="python"))
        )
        isolated_input = ModelInput.model_validate(
            copy.deepcopy(model_input.model_dump(mode="python"))
        )
        try:
            raw_response = await self._router.generate(
                isolated_request,
                isolated_input,
            )
            return ModelResponse.model_validate(
                copy.deepcopy(raw_response.model_dump(mode="python"))
            )
        except ModelProviderUnavailable:
            raise
        except Exception as error:
            raise ModelGatewayError("model provider failed") from error
