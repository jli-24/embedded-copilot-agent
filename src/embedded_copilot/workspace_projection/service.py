from __future__ import annotations

import copy
import hashlib
from pydantic import ValidationError

from embedded_copilot.engineering_generation.contracts import (
    FirmwareArtifact,
    HardwareDesignArtifact,
)

from .contracts import ProjectionStatus, WorkspaceArtifact, WorkspaceChangeProposal
from .exceptions import WorkspaceProjectionRejected


class WorkspaceProjectionService:
    __slots__ = ()

    def project(self, artifact: WorkspaceArtifact) -> WorkspaceChangeProposal:
        try:
            checked = self._validate_artifact(artifact)
            if isinstance(checked, FirmwareArtifact):
                filenames = checked.files
            else:
                filenames = ("hardware-proposal.md", "bom-proposal.md")
            proposal_id = (
                "proposal-"
                + hashlib.sha256(
                    (
                        checked.project_id
                        + "|"
                        + checked.artifact_id
                        + "|"
                        + checked.fingerprint
                    ).encode("utf-8")
                ).hexdigest()[:24]
            )
            return WorkspaceChangeProposal.create(
                proposal_id=proposal_id,
                project_id=checked.project_id,
                artifact_id=checked.artifact_id,
                artifact_type=checked.artifact_type.value,
                filenames=tuple(filenames),
                artifact_fingerprint=checked.fingerprint,
                status=ProjectionStatus.WAITING_APPROVAL,
                requires_approval=True,
            )
        except (TypeError, ValueError, ValidationError) as error:
            raise WorkspaceProjectionRejected() from error

    @staticmethod
    def _validate_artifact(artifact: object) -> WorkspaceArtifact:
        if type(artifact) is FirmwareArtifact:
            return FirmwareArtifact.model_validate(
                copy.deepcopy(artifact.model_dump(mode="python"))
            )
        if type(artifact) is HardwareDesignArtifact:
            return HardwareDesignArtifact.model_validate(
                copy.deepcopy(artifact.model_dump(mode="python"))
            )
        raise TypeError("artifact is invalid")
