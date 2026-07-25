from __future__ import annotations

import copy
from collections.abc import Sequence
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator

from embedded_copilot.copilot.models import (
    SessionApprovalStatus,
    WorkspaceFileType,
)
from embedded_copilot.copilot.workspace import ProjectWorkspace
from embedded_copilot.intelligence._validation import (
    safe_identifier,
    safe_text,
    safe_text_tuple,
)
from embedded_copilot.intelligence.models import (
    IntelligenceContractModel,
    ModelResponse,
)
from embedded_copilot.knowledge.source import (
    KnowledgeEvidence,
    KnowledgeSourceType,
)

_MISSING_CONTEXT_FIELDS = (
    "mcu_variant",
    "board",
    "sdk_version",
    "clock_context",
    "pin_context",
)


class ESP32HandoffType(StrEnum):
    HARDWARE_REVIEW = "HARDWARE_REVIEW"
    FIRMWARE = "FIRMWARE"


def _target_platform(value: object) -> str:
    candidate = safe_text(value, field="target_platform", max_length=128)
    normalized = candidate.casefold()
    if normalized != "esp32" and not normalized.startswith("esp32-"):
        raise ValueError("target platform is not ESP32 scoped")
    return candidate


def _identifier_tuple(value: object, *, field: str) -> object:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return value
    isolated = copy.deepcopy(value)
    identifiers = tuple(safe_identifier(item, field=field) for item in isolated)
    if len({item.casefold() for item in identifiers}) != len(identifiers):
        raise ValueError(f"{field} must be unique")
    return identifiers


class ESP32EngineeringInput(IntelligenceContractModel):
    target_platform: str
    datasheet_ids: tuple[str, ...] = Field(min_length=1)
    firmware_ids: tuple[str, ...] = Field(min_length=1)
    requirement_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("target_platform", mode="before")
    @classmethod
    def validate_target_platform(cls, value: object) -> str:
        return _target_platform(value)

    @field_validator(
        "datasheet_ids",
        "firmware_ids",
        "requirement_ids",
        mode="before",
    )
    @classmethod
    def validate_reference_ids(cls, value: object, info) -> object:
        return _identifier_tuple(value, field=info.field_name)


class ESP32EngineeringContext(IntelligenceContractModel):
    target_platform: str
    mcu_variant: str | None = None
    board: str | None = None
    sdk_version: str | None = None
    clock_context: str | None = None
    pin_context: str | None = None

    @field_validator("target_platform", mode="before")
    @classmethod
    def validate_target_platform(cls, value: object) -> str:
        return _target_platform(value)

    @field_validator(
        "mcu_variant",
        "board",
        "sdk_version",
        "clock_context",
        "pin_context",
        mode="before",
    )
    @classmethod
    def validate_optional_context(cls, value: object, info) -> str | None:
        if value is None:
            return None
        return safe_text(value, field=info.field_name, max_length=256)


class ESP32EngineeringHandoff(IntelligenceContractModel):
    workspace_session_id: str
    target_platform: str
    handoff_type: ESP32HandoffType
    datasheet_ids: tuple[str, ...]
    firmware_ids: tuple[str, ...]
    requirement_ids: tuple[str, ...]
    candidate_evidence: tuple[KnowledgeEvidence, ...] = ()
    reasoning_suggestions: tuple[str, ...] = ()
    missing_context: tuple[str, ...] = ()
    requires_engineering_validation: Literal[True] = True

    @field_validator("workspace_session_id", mode="before")
    @classmethod
    def validate_workspace_session_id(cls, value: object) -> str:
        return safe_identifier(value, field="workspace_session_id")

    @field_validator("target_platform", mode="before")
    @classmethod
    def validate_target_platform(cls, value: object) -> str:
        return _target_platform(value)

    @field_validator(
        "datasheet_ids",
        "firmware_ids",
        "requirement_ids",
        mode="before",
    )
    @classmethod
    def validate_reference_ids(cls, value: object, info) -> object:
        return _identifier_tuple(value, field=info.field_name)

    @field_validator("reasoning_suggestions", mode="before")
    @classmethod
    def validate_reasoning_suggestions(cls, value: object) -> object:
        return safe_text_tuple(
            value,
            field="reasoning_suggestion",
            max_length=4096,
        )

    @field_validator("missing_context", mode="before")
    @classmethod
    def validate_missing_context(cls, value: object) -> object:
        normalized = _identifier_tuple(value, field="missing_context")
        if isinstance(normalized, tuple) and any(
            item not in _MISSING_CONTEXT_FIELDS for item in normalized
        ):
            raise ValueError("missing context field is invalid")
        return normalized


class ESP32EngineeringHandoffAdapter:
    """Builds metadata-only handoffs; Engineering Agents must revalidate them."""

    def prepare(
        self,
        *,
        workspace: ProjectWorkspace,
        engineering_input: ESP32EngineeringInput,
        engineering_context: ESP32EngineeringContext,
        candidate_evidence: Sequence[KnowledgeEvidence] = (),
        reasoning_suggestions: Sequence[ModelResponse] = (),
    ) -> ESP32EngineeringHandoff:
        isolated_workspace = ProjectWorkspace.model_validate(
            copy.deepcopy(workspace.model_dump(mode="python"))
        )
        isolated_input = ESP32EngineeringInput.model_validate(
            copy.deepcopy(engineering_input.model_dump(mode="python"))
        )
        isolated_context = ESP32EngineeringContext.model_validate(
            copy.deepcopy(engineering_context.model_dump(mode="python"))
        )
        if (
            isolated_input.target_platform.casefold()
            != isolated_context.target_platform.casefold()
        ):
            raise ValueError("target platform context is inconsistent")

        self._validate_workspace_bindings(isolated_workspace, isolated_input)
        evidence = self._validate_evidence(candidate_evidence)
        suggestions = self._project_suggestions(reasoning_suggestions)
        context_values = (
            isolated_context.mcu_variant,
            isolated_context.board,
            isolated_context.sdk_version,
            isolated_context.clock_context,
            isolated_context.pin_context,
        )
        missing_context = tuple(
            field
            for field, value in zip(
                _MISSING_CONTEXT_FIELDS,
                context_values,
                strict=True,
            )
            if value is None
        )
        firmware_ready = (
            isolated_workspace.session.approval_status is SessionApprovalStatus.APPROVED
            and bool(isolated_workspace.session.artifact_ids)
        )
        return ESP32EngineeringHandoff(
            workspace_session_id=isolated_workspace.session.session_id,
            target_platform=isolated_input.target_platform,
            handoff_type=(
                ESP32HandoffType.FIRMWARE
                if firmware_ready
                else ESP32HandoffType.HARDWARE_REVIEW
            ),
            datasheet_ids=isolated_input.datasheet_ids,
            firmware_ids=isolated_input.firmware_ids,
            requirement_ids=isolated_input.requirement_ids,
            candidate_evidence=evidence,
            reasoning_suggestions=suggestions,
            missing_context=missing_context,
        )

    @staticmethod
    def _validate_workspace_bindings(
        workspace: ProjectWorkspace,
        engineering_input: ESP32EngineeringInput,
    ) -> None:
        file_types = {
            item.file_id.casefold(): item.file_type for item in workspace.files
        }
        bindings = (
            (engineering_input.datasheet_ids, WorkspaceFileType.DATASHEET),
            (engineering_input.firmware_ids, WorkspaceFileType.SOURCE_CODE),
            (engineering_input.requirement_ids, WorkspaceFileType.OTHER),
        )
        for identifiers, expected_type in bindings:
            if any(
                file_types.get(identifier.casefold()) is not expected_type
                for identifier in identifiers
            ):
                raise ValueError("workspace reference is invalid")

    @staticmethod
    def _validate_evidence(
        values: Sequence[KnowledgeEvidence],
    ) -> tuple[KnowledgeEvidence, ...]:
        evidence = tuple(
            KnowledgeEvidence.model_validate(
                copy.deepcopy(value.model_dump(mode="python"))
            )
            for value in values
        )
        if any(item.source_type is KnowledgeSourceType.GENERATED for item in evidence):
            raise ValueError("generated candidate is not bound")
        if len({item.source_id.casefold() for item in evidence}) != len(evidence):
            raise ValueError("candidate source identifiers must be unique")
        return evidence

    @staticmethod
    def _project_suggestions(
        values: Sequence[ModelResponse],
    ) -> tuple[str, ...]:
        return tuple(
            ModelResponse.model_validate(
                copy.deepcopy(value.model_dump(mode="python"))
            ).text
            for value in values
        )
