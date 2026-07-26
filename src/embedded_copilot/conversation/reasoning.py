from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.conversation.models import ReasoningOutput


@runtime_checkable
class ReasoningPort(Protocol):
    async def reason(
        self,
        *,
        user_message_summary: str,
        context_summaries: tuple[str, ...],
        task_intent: str,
    ) -> ReasoningOutput: ...
