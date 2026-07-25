from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from embedded_copilot.copilot.context import DesignSessionContext
from embedded_copilot.copilot.models import (
    SessionApprovalStatus,
    WorkspaceFileSource,
    WorkspaceFileStatus,
    WorkspaceFileType,
)
from embedded_copilot.copilot.session import create_session
from embedded_copilot.copilot.workspace import (
    ProjectWorkspace,
    WorkspaceFile,
    create_workspace,
    track_file,
)
from embedded_copilot.intelligence.esp32 import (
    ESP32EngineeringContext,
    ESP32EngineeringHandoffAdapter,
    ESP32EngineeringInput,
    ESP32HandoffType,
)
from embedded_copilot.intelligence.models import ModelResponse
from embedded_copilot.knowledge.source import (
    KnowledgeEvidence,
    KnowledgeSourceType,
)

UTC = timezone.utc
CREATED = datetime(2026, 7, 26, 8, 0, tzinfo=UTC)


def _file(
    identifier: str,
    filename: str,
    file_type: WorkspaceFileType,
    minute: int,
) -> WorkspaceFile:
    return WorkspaceFile(
        file_id=identifier,
        filename=filename,
        file_type=file_type,
        size_bytes=0,
        source=WorkspaceFileSource.INPUT,
        status=WorkspaceFileStatus.REFERENCED,
        created_at=CREATED + timedelta(minutes=minute),
    )


def _workspace(*, approved: bool = False) -> ProjectWorkspace:
    context = create_session(
        session_id="session:1",
        project_name="ESP32 Preparation",
        user_requirement="Prepare metadata for independent engineering review.",
        created_at=CREATED,
    )
    if approved:
        payload = context.model_dump(mode="python")
        payload["approval_status"] = SessionApprovalStatus.APPROVED
        payload["artifact_ids"] = ("artifact:1",)
        context = DesignSessionContext.model_validate(payload)
    workspace = create_workspace(context)
    workspace = track_file(
        workspace,
        _file("datasheet:1", "esp32-s3.pdf", WorkspaceFileType.DATASHEET, 1),
    )
    workspace = track_file(
        workspace,
        _file("firmware:1", "main.c", WorkspaceFileType.SOURCE_CODE, 2),
    )
    return track_file(
        workspace,
        _file("requirement:1", "requirements.md", WorkspaceFileType.OTHER, 3),
    )


def _input() -> ESP32EngineeringInput:
    return ESP32EngineeringInput(
        target_platform="ESP32-S3",
        datasheet_ids=("datasheet:1",),
        firmware_ids=("firmware:1",),
        requirement_ids=("requirement:1",),
    )


def test_target_platform_is_explicit_and_esp32_scoped() -> None:
    with pytest.raises(ValidationError):
        ESP32EngineeringInput.model_validate(
            {
                "datasheet_ids": ("datasheet:1",),
                "firmware_ids": ("firmware:1",),
                "requirement_ids": ("requirement:1",),
            }
        )
    with pytest.raises(ValidationError):
        ESP32EngineeringInput(
            target_platform="STM32F4",
            datasheet_ids=("datasheet:1",),
            firmware_ids=("firmware:1",),
            requirement_ids=("requirement:1",),
        )


def test_unapproved_workspace_only_creates_hardware_review_handoff() -> None:
    handoff = ESP32EngineeringHandoffAdapter().prepare(
        workspace=_workspace(),
        engineering_input=_input(),
        engineering_context=ESP32EngineeringContext(target_platform="ESP32-S3"),
    )

    assert handoff.handoff_type is ESP32HandoffType.HARDWARE_REVIEW
    assert handoff.requires_engineering_validation is True
    assert set(handoff.missing_context) == {
        "mcu_variant",
        "board",
        "sdk_version",
        "clock_context",
        "pin_context",
    }


def test_approved_workspace_can_create_firmware_handoff() -> None:
    handoff = ESP32EngineeringHandoffAdapter().prepare(
        workspace=_workspace(approved=True),
        engineering_input=_input(),
        engineering_context=ESP32EngineeringContext(
            target_platform="ESP32-S3",
            mcu_variant="ESP32-S3R8",
            board="ESP32-S3-DevKitC-1",
            sdk_version="ESP-IDF 5.2",
            clock_context="Caller supplied clock metadata.",
            pin_context="Caller supplied pin metadata.",
        ),
    )

    assert handoff.handoff_type is ESP32HandoffType.FIRMWARE
    assert handoff.missing_context == ()
    assert handoff.datasheet_ids == ("datasheet:1",)
    assert handoff.firmware_ids == ("firmware:1",)
    assert handoff.requirement_ids == ("requirement:1",)


@pytest.mark.parametrize(
    ("field", "identifier"),
    (
        ("datasheet_ids", "firmware:1"),
        ("firmware_ids", "datasheet:1"),
        ("requirement_ids", "datasheet:1"),
        ("datasheet_ids", "missing:1"),
    ),
)
def test_workspace_bindings_and_file_types_are_enforced(
    field: str,
    identifier: str,
) -> None:
    payload = _input().model_dump(mode="python")
    payload[field] = (identifier,)

    with pytest.raises(ValueError, match="workspace reference is invalid"):
        ESP32EngineeringHandoffAdapter().prepare(
            workspace=_workspace(),
            engineering_input=ESP32EngineeringInput.model_validate(payload),
            engineering_context=ESP32EngineeringContext(target_platform="ESP32-S3"),
        )


def test_target_context_must_match_caller_input() -> None:
    with pytest.raises(ValueError, match="target platform context is inconsistent"):
        ESP32EngineeringHandoffAdapter().prepare(
            workspace=_workspace(),
            engineering_input=_input(),
            engineering_context=ESP32EngineeringContext(target_platform="ESP32-C3"),
        )


def test_candidate_knowledge_and_reasoning_remain_unvalidated_suggestions() -> None:
    evidence = KnowledgeEvidence(
        source_id="datasheet:external",
        source_type=KnowledgeSourceType.DATASHEET,
        summary="Candidate source summary requiring Engineering Agent validation.",
        relevance_score=0.9,
    )
    response = ModelResponse(
        text="GPIO4 may be worth reviewing; this is not an Engineering Fact.",
        source="test-provider",
    )

    handoff = ESP32EngineeringHandoffAdapter().prepare(
        workspace=_workspace(),
        engineering_input=_input(),
        engineering_context=ESP32EngineeringContext(target_platform="ESP32-S3"),
        candidate_evidence=(evidence,),
        reasoning_suggestions=(response,),
    )

    assert handoff.candidate_evidence == (evidence,)
    assert handoff.reasoning_suggestions == (response.text,)
    assert handoff.requires_engineering_validation is True
    assert "artifact_evidence" not in type(handoff).model_fields
    assert "agent_decision" not in type(handoff).model_fields


def test_generated_candidate_without_visible_source_binding_is_rejected() -> None:
    generated = KnowledgeEvidence(
        source_id="generated:1",
        source_type=KnowledgeSourceType.GENERATED,
        summary="Derived candidate summary.",
        relevance_score=0.5,
    )

    with pytest.raises(ValueError, match="generated candidate is not bound"):
        ESP32EngineeringHandoffAdapter().prepare(
            workspace=_workspace(),
            engineering_input=_input(),
            engineering_context=ESP32EngineeringContext(target_platform="ESP32-S3"),
            candidate_evidence=(generated,),
        )


def test_handoff_contracts_are_metadata_only() -> None:
    assert set(ESP32EngineeringInput.model_fields) == {
        "target_platform",
        "datasheet_ids",
        "firmware_ids",
        "requirement_ids",
    }
    for forbidden in (
        "content",
        "file_body",
        "binary",
        "pcb",
        "eda",
        "flash_operation",
    ):
        assert forbidden not in ESP32EngineeringInput.model_fields
