from __future__ import annotations

import json
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from embedded_copilot.workspace_runtime import (
    ApprovalContext,
    ChangeProposal,
    ValidationResult,
)


def _reject_nonfinite_json_number(value: str) -> object:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


class _VSCodeContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class VSCodeCapability(StrEnum):
    READ_CONTEXT = "READ_CONTEXT"
    ANALYZE_CODE = "ANALYZE_CODE"
    ANALYZE_BUILD = "ANALYZE_BUILD"
    REVIEW_DIFF = "REVIEW_DIFF"
    CREATE_PROPOSAL = "CREATE_PROPOSAL"
    APPLY_APPROVED_CHANGE = "APPLY_APPROVED_CHANGE"


DEFAULT_CAPABILITIES: tuple[VSCodeCapability, ...] = (
    VSCodeCapability.READ_CONTEXT,
    VSCodeCapability.ANALYZE_CODE,
    VSCodeCapability.ANALYZE_BUILD,
    VSCodeCapability.REVIEW_DIFF,
    VSCodeCapability.CREATE_PROPOSAL,
)


class MCPToolName(StrEnum):
    INSPECT_WORKSPACE_CONTEXT = "inspect_workspace_context"
    ANALYZE_CODE = "analyze_code"
    ANALYZE_BUILD_LOG = "analyze_build_log"
    REVIEW_DIFF = "review_diff"
    CREATE_CHANGE_PROPOSAL = "create_change_proposal"
    APPLY_APPROVED_CHANGE = "apply_approved_change"


class ChangeProposalResult(_VSCodeContract):
    proposal: ChangeProposal
    validation: ValidationResult


class ApprovedChangeRequest(_VSCodeContract):
    proposal: ChangeProposal
    approval: ApprovalContext


class MCPToolResult(_VSCodeContract):
    tool_name: MCPToolName | None
    is_error: bool
    payload_json: str | None = None
    error_code: (
        Literal[
            "invalid_arguments",
            "unknown_tool",
            "capability_denied",
            "runtime_unavailable",
        ]
        | None
    ) = None

    @field_validator("payload_json")
    @classmethod
    def validate_canonical_payload(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            decoded = json.loads(
                value,
                parse_constant=_reject_nonfinite_json_number,
            )
            if not isinstance(decoded, dict):
                raise ValueError("payload must be a JSON object")
            canonical = json.dumps(
                decoded,
                allow_nan=False,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError):
            raise ValueError("payload must be canonical JSON") from None
        if value != canonical:
            raise ValueError("payload must be canonical JSON")
        return value

    @model_validator(mode="after")
    def validate_result_boundary(self) -> "MCPToolResult":
        if self.is_error:
            if self.error_code is None or self.payload_json is not None:
                raise ValueError("error result requires only an error code")
        elif (
            self.tool_name is None
            or self.error_code is not None
            or self.payload_json is None
        ):
            raise ValueError("success result requires only a payload")
        return self
