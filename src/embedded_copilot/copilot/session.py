from __future__ import annotations

import copy
from datetime import datetime

from embedded_copilot.copilot.context import DesignSessionContext
from embedded_copilot.copilot.models import (
    ArtifactDecisionView,
    ArtifactEvidenceView,
    ArtifactView,
    DesignStage,
    SessionApprovalStatus,
    safe_identifier,
    utc_datetime,
)
from embedded_copilot.hardware_design.approval import DesignApprovalStatus
from embedded_copilot.hardware_design.artifact import HardwareDesignArtifact

_STAGE_INDEX = {stage: index for index, stage in enumerate(DesignStage)}


def create_session(
    *,
    session_id: str,
    project_name: str,
    user_requirement: str,
    created_at: datetime,
) -> DesignSessionContext:
    return DesignSessionContext(
        session_id=session_id,
        project_name=project_name,
        user_requirement=user_requirement,
        created_at=created_at,
        updated_at=created_at,
    )


def advance_stage(
    context: DesignSessionContext,
    stage: DesignStage,
    *,
    updated_at: datetime,
) -> DesignSessionContext:
    isolated = _context(context)
    timestamp = _newer_timestamp(isolated, updated_at)
    target = DesignStage(stage)
    if _STAGE_INDEX[target] <= _STAGE_INDEX[isolated.current_stage]:
        raise ValueError("session stage must move forward")
    payload = isolated.model_dump(mode="python")
    payload.update(current_stage=target, updated_at=timestamp)
    return DesignSessionContext.model_validate(payload)


def bind_artifact(
    context: DesignSessionContext,
    *,
    artifact_id: str,
    artifact: HardwareDesignArtifact,
    updated_at: datetime,
) -> DesignSessionContext:
    isolated_context = _context(context)
    isolated_artifact = _artifact(artifact)
    identifier = safe_identifier(artifact_id, field="artifact_id")
    timestamp = _newer_timestamp(isolated_context, updated_at)
    if identifier.casefold() in {
        item.casefold() for item in isolated_context.artifact_ids
    }:
        raise ValueError("artifact reference already exists")
    if isolated_artifact.approval.status is DesignApprovalStatus.MODIFIED:
        raise ValueError("modified Artifact approval is unsupported")
    approval_status = SessionApprovalStatus(isolated_artifact.approval.status.value)
    new_decision_ids = tuple(item.decision_id for item in isolated_artifact.decisions)
    combined_decisions = (*isolated_context.decision_ids, *new_decision_ids)
    if len({item.casefold() for item in combined_decisions}) != len(combined_decisions):
        raise ValueError("artifact decision reference already exists")
    payload = isolated_context.model_dump(mode="python")
    payload.update(
        artifact_ids=(*isolated_context.artifact_ids, identifier),
        decision_ids=combined_decisions,
        approval_status=approval_status,
        updated_at=timestamp,
    )
    return DesignSessionContext.model_validate(payload)


def project_artifact_view(
    *,
    artifact_id: str,
    artifact: HardwareDesignArtifact,
) -> ArtifactView:
    isolated = _artifact(artifact)
    return ArtifactView(
        artifact_id=artifact_id,
        project_name=isolated.blueprint.project_name,
        target_platform=isolated.blueprint.target_platform,
        components=tuple(module.name for module in isolated.blueprint.modules),
        limitations=isolated.blueprint.limitations,
        evidence=tuple(
            ArtifactEvidenceView(
                evidence_id=item.evidence_id,
                source_id=item.source_id,
                summary=item.content_summary,
            )
            for item in isolated.evidence
        ),
        decisions=tuple(
            ArtifactDecisionView(
                decision_id=item.decision_id,
                decision=item.decision,
                reason=item.reason,
                confidence=item.confidence,
                status=item.status,
                evidence_ids=item.evidence_ids,
            )
            for item in isolated.decisions
        ),
        approval_status=isolated.approval.status,
    )


def _context(context: DesignSessionContext) -> DesignSessionContext:
    if not isinstance(context, DesignSessionContext):
        raise TypeError("session context is invalid")
    return DesignSessionContext.model_validate(
        copy.deepcopy(context.model_dump(mode="python"))
    )


def _artifact(artifact: HardwareDesignArtifact) -> HardwareDesignArtifact:
    if not isinstance(artifact, HardwareDesignArtifact):
        raise TypeError("hardware design Artifact is invalid")
    return HardwareDesignArtifact.model_validate(
        copy.deepcopy(artifact.model_dump(mode="python"))
    )


def _newer_timestamp(
    context: DesignSessionContext,
    value: datetime,
) -> datetime:
    timestamp = utc_datetime(value, field="updated_at")
    if timestamp <= context.updated_at:
        raise ValueError("session update timestamp must increase")
    return timestamp
