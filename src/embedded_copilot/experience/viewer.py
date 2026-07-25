from __future__ import annotations

import copy

from embedded_copilot.experience.existing_contracts import (
    ArtifactView,
    ProjectWorkspace,
)
from embedded_copilot.experience.models import (
    BlueprintProjection,
    ExperienceRequest,
    ViewerState,
    ViewerStatus,
)
from embedded_copilot.experience.ports import (
    ArtifactViewReadPort,
    BlueprintReadPort,
    WorkspaceReadPort,
)
from embedded_copilot.experience.presentation import (
    ArtifactDecisionSummary,
    ArtifactEvidenceSummary,
    ArtifactPresentation,
    ArtifactViewerResponse,
    BlueprintSummary,
    ExperienceProjectionUnavailable,
)


class ArtifactViewerService:
    def __init__(
        self,
        *,
        workspace_port: WorkspaceReadPort,
        artifact_port: ArtifactViewReadPort,
        blueprint_port: BlueprintReadPort,
    ) -> None:
        self._workspace_port = workspace_port
        self._artifact_port = artifact_port
        self._blueprint_port = blueprint_port

    def get_artifacts(self, request: ExperienceRequest) -> ArtifactViewerResponse:
        workspace = ProjectWorkspace.model_validate(
            copy.deepcopy(
                self._workspace_port.get(request.session_id).model_dump(mode="python")
            )
        )
        if workspace.session.session_id.casefold() != request.session_id.casefold():
            raise ExperienceProjectionUnavailable(
                "Workspace projection session identity is inconsistent."
            )
        items = tuple(
            self._artifact(request.session_id, artifact_id)
            for artifact_id in workspace.session.artifact_ids
        )
        return ArtifactViewerResponse(
            session_id=request.session_id,
            viewer_state=ViewerState(
                status=ViewerStatus.READY if items else ViewerStatus.EMPTY,
            ),
            artifacts=items,
        )

    def _artifact(self, session_id: str, artifact_id: str) -> ArtifactPresentation:
        raw_view = self._artifact_port.get(session_id, artifact_id)
        if raw_view is None:
            raise ExperienceProjectionUnavailable("Artifact projection is unavailable.")
        view = ArtifactView.model_validate(
            copy.deepcopy(raw_view.model_dump(mode="python"))
        )
        if view.artifact_id.casefold() != artifact_id.casefold():
            raise ExperienceProjectionUnavailable(
                "Artifact projection identity is inconsistent."
            )
        blueprint = self._blueprint(session_id, artifact_id)
        return ArtifactPresentation(
            session_id=session_id,
            artifact_id=artifact_id,
            project_summary=view.project_name,
            target_platform=view.target_platform,
            blueprint_summary=blueprint,
            evidence_summary=tuple(
                ArtifactEvidenceSummary(
                    evidence_id=item.evidence_id,
                    source_id=item.source_id,
                    summary=item.summary,
                )
                for item in view.evidence
            ),
            decision_summary=tuple(
                ArtifactDecisionSummary(
                    decision_id=item.decision_id,
                    summary=item.decision,
                    reason=item.reason,
                    confidence=item.confidence,
                    status=item.status.value,
                    evidence_ids=item.evidence_ids,
                )
                for item in view.decisions
            ),
            limitations=view.limitations,
            approval_status=view.approval_status.value,
        )

    def _blueprint(self, session_id: str, artifact_id: str) -> BlueprintSummary:
        raw_projection = self._blueprint_port.get(session_id, artifact_id)
        if raw_projection is None:
            return BlueprintSummary(
                viewer_state=ViewerState(
                    status=ViewerStatus.UNAVAILABLE,
                    detail="Blueprint projection is unavailable.",
                )
            )
        projection = BlueprintProjection.model_validate(
            copy.deepcopy(raw_projection.model_dump(mode="python"))
        )
        if (
            projection.session_id.casefold() != session_id.casefold()
            or projection.artifact_id.casefold() != artifact_id.casefold()
        ):
            raise ExperienceProjectionUnavailable(
                "Blueprint projection identity is inconsistent."
            )
        if projection.edges:
            state = ViewerState(status=ViewerStatus.READY)
        elif projection.nodes:
            state = ViewerState(
                status=ViewerStatus.EMPTY,
                detail="Blueprint relationships are unresolved.",
            )
        else:
            state = ViewerState(
                status=ViewerStatus.UNAVAILABLE,
                detail="No verified relationship available",
            )
        return BlueprintSummary(
            viewer_state=state,
            nodes=projection.nodes,
            edges=projection.edges,
        )
