from __future__ import annotations

from typing import Protocol

from embedded_copilot.conversation.models import ReasoningOutput


class ReasoningPort(Protocol):
    async def reason(
        self,
        *,
        user_message_summary: str,
        context_summaries: tuple[str, ...],
        task_intent: str,
    ) -> ReasoningOutput: ...
