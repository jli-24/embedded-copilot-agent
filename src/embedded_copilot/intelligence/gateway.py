from __future__ import annotations

import copy
from collections.abc import Sequence

from embedded_copilot.intelligence.exceptions import (
    ModelGatewayError,
    ModelProviderUnavailable,
)
from embedded_copilot.intelligence.models import ModelInput, ModelResponse
from embedded_copilot.intelligence.providers.base import ModelProvider
from embedded_copilot.intelligence.routing import select_provider, validate_providers
from embedded_copilot.schemas.model import ModelRequest


class ModelGateway:
    """Request-scoped model invocation boundary returning suggestions only."""

    def __init__(self, providers: Sequence[ModelProvider]) -> None:
        self._providers = validate_providers(tuple(providers))

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
        provider = select_provider(self._providers, isolated_request.task_type)
        try:
            raw_response = await provider.generate(isolated_request, isolated_input)
            response = ModelResponse.model_validate(
                copy.deepcopy(raw_response.model_dump(mode="python"))
            )
        except ModelProviderUnavailable:
            raise
        except Exception as exc:
            raise ModelGatewayError("model provider failed") from exc
        if response.source.casefold() != provider.provider_id.casefold():
            raise ModelGatewayError("model provider returned an invalid response")
        return response
