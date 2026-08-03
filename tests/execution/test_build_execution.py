from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

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
    ESPIdfBuildInvocation,
    HostBuildResult,
    build_approval_fingerprint,
    build_execution_request_fingerprint,
    create_build_execution_service,
    host_build_result_fingerprint,
)
from embedded_copilot.firmware_agent import (
    FirmwareArtifactProjection,
    FirmwareArtifactType,
    FirmwarePlatform,
    FirmwareProposal,
    FirmwareSourceFile,
    firmware_artifact_fingerprint,
    firmware_proposal_fingerprint,
    firmware_source_file_fingerprint,
)

NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)
FP = "sha256:" + "a" * 64


def _proposal() -> FirmwareProposal:
    files = tuple(
        _file(path, purpose, content)
        for path, purpose, content in (
            ("CMakeLists.txt", "BUILD_ENTRY", "project(camera_demo)\n"),
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
        "count": 2,
        "reference_id": "firmware-1",
        "timestamp": NOW,
    }
    event = EngineeringEvent(
        **event_values,
        fingerprint=engineering_event_fingerprint(**event_values),
    )
    values = {
        "request_id": "firmware-1",
        "project_id": "project-1",
        "platform": FirmwarePlatform.ESP_IDF,
        "source_context_fingerprint": FP,
        "source_workspace_fingerprint": "sha256:" + "b" * 64,
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


def _file(path: str, purpose: str, content: str) -> FirmwareSourceFile:
    values = {"logical_path": path, "purpose": purpose, "content": content}
    return FirmwareSourceFile(
        **values,
        fingerprint=firmware_source_file_fingerprint(**values),
    )


def _artifact(
    kind: FirmwareArtifactType, references: tuple[str, ...]
) -> FirmwareArtifactProjection:
    values = {"artifact_type": kind, "reference_ids": references}
    return FirmwareArtifactProjection(
        **values,
        fingerprint=firmware_artifact_fingerprint(**values),
    )


def _request(proposal: FirmwareProposal | None = None) -> BuildExecutionRequest:
    proposal = proposal or _proposal()
    approval_values = {
        "build_id": "build-1",
        "proposal_fingerprint": proposal.fingerprint,
        "status": BuildApprovalStatus.APPROVED,
        "reviewer": "engineer-1",
        "reviewed_at": NOW,
    }
    approval = BuildApproval(
        **approval_values,
        fingerprint=build_approval_fingerprint(**approval_values),
    )
    values = {
        "build_id": "build-1",
        "proposal": proposal,
        "approval": approval,
        "requested_at": NOW,
    }
    return BuildExecutionRequest(
        **values,
        fingerprint=build_execution_request_fingerprint(**values),
    )


class BuildPortFake:
    def __init__(self, result: HostBuildResult | Exception) -> None:
        self.result = result
        self.calls: list[ESPIdfBuildInvocation] = []

    async def build(self, request: ESPIdfBuildInvocation) -> HostBuildResult:
        self.calls.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result.model_copy(deep=True)


def _host_result(status: BuildStatus = BuildStatus.SUCCESS) -> HostBuildResult:
    values = {
        "status": status,
        "diagnostic_codes": () if status is BuildStatus.SUCCESS else ("COMPILER_ERROR",),
        "symbol_references": (),
    }
    return HostBuildResult(
        **values,
        fingerprint=host_build_result_fingerprint(**values),
    )


def test_build_contracts_are_strict_frozen_and_approval_bound() -> None:
    request = _request()

    with pytest.raises(ValidationError):
        request.build_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        BuildExecutionRequest.model_validate(
            {**request.model_dump(), "shell": "idf.py build"}
        )


def test_build_delegates_once_with_safe_projection_and_is_deterministic() -> None:
    request = _request()
    before = request.model_dump(mode="json")
    port = BuildPortFake(_host_result())
    service = create_build_execution_service(build_port=port)

    first = asyncio.run(service.execute(request))
    second = asyncio.run(
        create_build_execution_service(build_port=BuildPortFake(_host_result())).execute(
            request
        )
    )

    assert first.status is BuildStatus.SUCCESS
    assert first == second
    assert hash(first) == hash(second)
    assert len(port.calls) == 1
    invocation = port.calls[0]
    assert invocation.proposal_fingerprint == request.proposal.fingerprint
    assert invocation.source_file_fingerprints == tuple(
        sorted(item.fingerprint for item in request.proposal.files)
    )
    serialized = invocation.model_dump_json().lower()
    assert "content" not in serialized
    assert "logical_path" not in serialized
    assert "idf.py" not in serialized
    assert request.model_dump(mode="json") == before


def test_build_failure_is_sanitized_and_unapproved_build_is_not_called() -> None:
    failing = BuildPortFake(RuntimeError("C:\\secret\\project token=abc"))
    result = asyncio.run(
        create_build_execution_service(build_port=failing).execute(_request())
    )
    assert result.status is BuildStatus.UNAVAILABLE
    assert result.diagnostic_codes == ("BUILD_EXECUTION_UNAVAILABLE",)
    assert "secret" not in result.model_dump_json().lower()

    request = _request()
    approval_values = {
        "build_id": request.build_id,
        "proposal_fingerprint": request.proposal.fingerprint,
        "status": BuildApprovalStatus.REJECTED,
        "reviewer": "engineer-1",
        "reviewed_at": NOW,
    }
    approval = BuildApproval(
        **approval_values,
        fingerprint=build_approval_fingerprint(**approval_values),
    )
    values = {
        "build_id": request.build_id,
        "proposal": request.proposal,
        "approval": approval,
        "requested_at": request.requested_at,
    }
    rejected = BuildExecutionRequest(
        **values,
        fingerprint=build_execution_request_fingerprint(**values),
    )
    port = BuildPortFake(_host_result())
    blocked: BuildResult = asyncio.run(
        create_build_execution_service(build_port=port).execute(rejected)
    )
    assert blocked.status is BuildStatus.BLOCKED
    assert port.calls == []
