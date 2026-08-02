"""Safe Product Workspace projection for Engineering Chat."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.ai_runtime.exceptions import AIRequestRejected
from embedded_copilot.ai_runtime.models import (
    EngineeringChatContext,
    engineering_chat_context_fingerprint,
)
from embedded_copilot.product import EngineeringWorkspace


def project_engineering_workspace(
    workspace: EngineeringWorkspace,
) -> EngineeringChatContext:
    if type(workspace) is not EngineeringWorkspace:
        raise AIRequestRejected("engineering workspace was rejected") from None
    try:
        checked = EngineeringWorkspace.model_validate(workspace.model_copy(deep=True))
    except (TypeError, ValueError, ValidationError):
        raise AIRequestRejected("engineering workspace was rejected") from None
    references = tuple(
        sorted(
            reference.reference_id
            for stage in checked.stage_references
            for reference in stage.references
        )
    )
    decisions = tuple(sorted({item.decision for item in checked.decisions}))
    values = dict(
        project_id=checked.project_id,
        project_summary=checked.project_summary,
        current_stage=checked.session.current_stage.value,
        reference_ids=references,
        decision_summaries=decisions,
        workspace_fingerprint=checked.fingerprint,
    )
    return EngineeringChatContext(
        **values,
        fingerprint=engineering_chat_context_fingerprint(**values),
    )
