from __future__ import annotations

from typing import Protocol

from embedded_copilot.conversation.models import ReasoningOutput
from embedded_copilot.intelligence.gateway import ModelGateway
from embedded_copilot.intelligence.models import ModelInput
from embedded_copilot.schemas.model import ModelRequest


class ReasoningPort(Protocol):
    async def reason(
        self,
        request: ModelRequest,
        model_input: ModelInput,
    ) -> ReasoningOutput: ...


class GatewayReasoningAdapter:
    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway

    async def reason(
        self,
        request: ModelRequest,
        model_input: ModelInput,
    ) -> ReasoningOutput:
        response = await self._gateway.generate(request, model_input)
        return ReasoningOutput(response=response)
