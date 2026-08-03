"""Deterministic projection-only v1.3 ports for local development."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from embedded_copilot.engineering_events import (
    EngineeringEvent,
    EngineeringEventType,
    engineering_event_fingerprint,
)
from embedded_copilot.execution import (
    BuildApproval,
    BuildApprovalStatus,
    BuildExecutionRequest,
    BuildResult,
    BuildStatus,
    build_approval_fingerprint,
    build_result_fingerprint,
)
from embedded_copilot.firmware_agent import (
    FirmwareArtifactProjection,
    FirmwareArtifactType,
    FirmwareGenerationRequest,
    FirmwareProposal,
    FirmwareSourceFile,
    firmware_artifact_fingerprint,
    firmware_proposal_fingerprint,
    firmware_source_file_fingerprint,
)

_DEMO_TIME = datetime(2026, 8, 12, 8, tzinfo=UTC)


class DemoFirmwareAgentPort:
    __slots__ = ()

    async def generate(self, request: FirmwareGenerationRequest) -> FirmwareProposal:
        checked = FirmwareGenerationRequest.model_validate(
            request.model_copy(deep=True)
        )
        files = tuple(
            _file(path, purpose, content)
            for path, purpose, content in (
                ("CMakeLists.txt", "BUILD_ENTRY", "project(embedded_demo)\n"),
                ("main/main.c", "APPLICATION_ENTRY", "void app_main(void) {}\n"),
            )
        )
        references = tuple(sorted(item.fingerprint for item in files))
        artifacts = tuple(_artifact(kind, references) for kind in FirmwareArtifactType)
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
            "knowledge_fingerprints": (),
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


class DemoBuildExecutionPort:
    __slots__ = ()

    async def execute(self, request: BuildExecutionRequest) -> BuildResult:
        checked = BuildExecutionRequest.model_validate(
            request.model_copy(deep=True)
        )
        approved = checked.approval.status is BuildApprovalStatus.APPROVED
        values = {
            "build_id": checked.build_id,
            "project_id": checked.proposal.project_id,
            "proposal_fingerprint": checked.proposal.fingerprint,
            "status": BuildStatus.UNAVAILABLE if approved else BuildStatus.BLOCKED,
            "diagnostic_codes": (
                ("DEMO_EXECUTION_NOT_AVAILABLE",)
                if approved
                else ("BUILD_APPROVAL_REQUIRED",)
            ),
            "symbol_references": (),
            "observed_at": checked.requested_at,
        }
        return BuildResult(**values, fingerprint=build_result_fingerprint(**values))


class DemoBuildApprovalPort:
    __slots__ = ()

    def resolve(
        self,
        *,
        approval_reference_id: str,
        build_id: str,
        proposal_fingerprint: str,
    ) -> BuildApproval:
        values = {
            "build_id": build_id,
            "proposal_fingerprint": proposal_fingerprint,
            "status": BuildApprovalStatus.REJECTED,
            "reviewer": approval_reference_id,
            "reviewed_at": _DEMO_TIME,
        }
        return BuildApproval(
            **values,
            fingerprint=build_approval_fingerprint(**values),
        )


class InMemoryWebProjectionRepository:
    __slots__ = ("_items",)

    def __init__(self) -> None:
        self._items: dict[str, BaseModel] = {}

    def save(self, key: str, value: BaseModel) -> None:
        self._items[key] = value.model_copy(deep=True)

    def load(self, key: str) -> BaseModel:
        return self._items[key].model_copy(deep=True)


def _file(path: str, purpose: str, content: str) -> FirmwareSourceFile:
    values = {"logical_path": path, "purpose": purpose, "content": content}
    return FirmwareSourceFile(
        **values,
        fingerprint=firmware_source_file_fingerprint(**values),
    )


def _artifact(
    kind: FirmwareArtifactType,
    references: tuple[str, ...],
) -> FirmwareArtifactProjection:
    values = {"artifact_type": kind, "reference_ids": references}
    return FirmwareArtifactProjection(
        **values,
        fingerprint=firmware_artifact_fingerprint(**values),
    )
