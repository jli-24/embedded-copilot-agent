"""Stateless Firmware Agent service."""

from __future__ import annotations

from embedded_copilot.engineering_events import (
    EngineeringEvent,
    EngineeringEventType,
    engineering_event_fingerprint,
)
from embedded_copilot.firmware_agent.exceptions import FirmwareGenerationRejected
from embedded_copilot.firmware_agent.generator import FirmwareReasoningGenerator
from embedded_copilot.firmware_agent.models import (
    FirmwareArtifactProjection,
    FirmwareArtifactType,
    FirmwareGenerationRequest,
    FirmwareProposal,
    firmware_artifact_fingerprint,
    firmware_proposal_fingerprint,
)


class FirmwareAgentService:
    __slots__ = ("_generator",)

    def __init__(self, generator: FirmwareReasoningGenerator) -> None:
        self._generator = generator

    async def generate(self, request: FirmwareGenerationRequest) -> FirmwareProposal:
        try:
            if type(request) is not FirmwareGenerationRequest:
                raise ValueError("typed request is required")
            checked = FirmwareGenerationRequest.model_validate(
                request.model_copy(deep=True)
            )
            files = await self._generator.generate(checked)
            references = tuple(sorted(item.fingerprint for item in files))
            artifacts = tuple(
                _artifact(artifact_type, references)
                for artifact_type in FirmwareArtifactType
            )
            event_values = {
                "sequence": 1,
                "event_type": EngineeringEventType.ARTIFACT_CREATED,
                "stage": "FIRMWARE",
                "status": "PROPOSED",
                "count": len(files),
                "reference_id": checked.request_id,
                "timestamp": checked.requested_at,
            }
            event = EngineeringEvent(
                **event_values,
                fingerprint=engineering_event_fingerprint(**event_values),
            )
            values = {
                "request_id": checked.request_id,
                "project_id": checked.context.project_id,
                "platform": checked.platform,
                "source_context_fingerprint": checked.context.fingerprint,
                "source_workspace_fingerprint": checked.context.workspace_fingerprint,
                "knowledge_fingerprints": tuple(
                    item.fingerprint for item in checked.knowledge
                ),
                "files": files,
                "artifacts": artifacts,
                "event": event,
                "candidate_semantics": "unverified",
                "review_required": True,
            }
            return FirmwareProposal(
                **values,
                fingerprint=firmware_proposal_fingerprint(**values),
            )
        except FirmwareGenerationRejected:
            raise
        except Exception:  # noqa: BLE001 - dependency failures are sanitized
            raise FirmwareGenerationRejected(
                "firmware generation was rejected"
            ) from None


def _artifact(
    artifact_type: FirmwareArtifactType,
    references: tuple[str, ...],
) -> FirmwareArtifactProjection:
    values = {"artifact_type": artifact_type, "reference_ids": references}
    return FirmwareArtifactProjection(
        **values,
        fingerprint=firmware_artifact_fingerprint(**values),
    )
