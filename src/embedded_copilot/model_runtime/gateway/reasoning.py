from __future__ import annotations

from dataclasses import dataclass

from embedded_copilot.conversation.models import ReasoningOutput
from embedded_copilot.conversation.reasoning import ReasoningPort
from embedded_copilot.intelligence.models import ModelInput
from embedded_copilot.model_runtime.gateway.model import ModelGateway
from embedded_copilot.schemas.model import (
    ModelInputType,
    ModelRequest,
    ModelTaskType,
)

_TASK_TYPES = {
    "CHAT": ModelTaskType.CHAT,
    "DEBUG": ModelTaskType.REASONING,
    "VISION_ANALYSIS": ModelTaskType.VISION,
    "DATASHEET_ANALYSIS": ModelTaskType.REASONING,
    "DESIGN_REVIEW": ModelTaskType.REASONING,
    "FIRMWARE": ModelTaskType.CODE,
    "KNOWLEDGE": ModelTaskType.REASONING,
    "GENERAL": ModelTaskType.CHAT,
}
_INPUT_TYPES = {
    "VISION_ANALYSIS": ModelInputType.IMAGE,
    "DATASHEET_ANALYSIS": ModelInputType.FILE,
}


@dataclass(frozen=True, slots=True)
class GatewayReasoningPort(ReasoningPort):
    _gateway: ModelGateway

    async def reason(
        self,
        *,
        user_message_summary: str,
        context_summaries: tuple[str, ...],
        task_intent: str,
    ) -> ReasoningOutput:
        try:
            task_type = _TASK_TYPES[task_intent]
        except KeyError as error:
            raise ValueError("reasoning task intent is invalid") from error
        response = await self._gateway.generate(
            ModelRequest(
                task_type=task_type,
                input_type=_INPUT_TYPES.get(task_intent, ModelInputType.TEXT),
                context_ids=("request:scoped",),
            ),
            ModelInput(
                message_summary=user_message_summary,
                context_summaries=context_summaries,
            ),
        )
        return ReasoningOutput(response=response)
