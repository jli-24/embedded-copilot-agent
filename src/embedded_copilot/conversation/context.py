from __future__ import annotations

from embedded_copilot.copilot.workspace import ProjectWorkspace
from embedded_copilot.intelligence.models import ModelInput


class ContextResolver:
    def __init__(self, *, max_message_summaries: int = 6) -> None:
        if not 0 <= max_message_summaries <= 20:
            raise ValueError("context summary limit is invalid")
        self._max_message_summaries = max_message_summaries

    def resolve(
        self,
        workspace: ProjectWorkspace,
        message_summary: str,
    ) -> ModelInput:
        isolated = ProjectWorkspace.model_validate(workspace.model_dump(mode="python"))
        recent = isolated.messages[-self._max_message_summaries :]
        summaries = (
            f"Project: {isolated.session.project_name}",
            f"Stage: {isolated.session.current_stage.value}",
            *(item.content_summary for item in recent),
        )
        return ModelInput(
            message_summary=message_summary,
            context_summaries=summaries,
        )
