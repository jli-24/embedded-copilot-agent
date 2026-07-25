from __future__ import annotations

import copy
from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from embedded_copilot.experience.existing_contracts import (
    safe_identifier,
    safe_optional_summary,
    safe_summary,
    utc_datetime,
)
from embedded_copilot.schemas.result import ContractModel
from embedded_copilot.schemas.knowledge_trace import KnowledgeTrace


class ExperienceContractModel(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class ViewerStatus(StrEnum):
    READY = "READY"
    EMPTY = "EMPTY"
    UNAVAILABLE = "UNAVAILABLE"


class ReviewIntentAction(StrEnum):
    REQUEST_REVIEW = "REQUEST_REVIEW"
    APPROVE_INTENT = "APPROVE_INTENT"
    REQUEST_CHANGE = "REQUEST_CHANGE"


class ReviewRecordStatus(StrEnum):
    RECORDED = "RECORDED"


class ViewerState(ExperienceContractModel):
    status: ViewerStatus
    detail: str | None = None

    @field_validator("detail", mode="before")
    @classmethod
    def validate_detail(cls, value: object) -> str | None:
        return safe_optional_summary(value, field="detail")


class ExperienceRequest(ExperienceContractModel):
    session_id: str

    @field_validator("session_id", mode="before")
    @classmethod
    def validate_session_id(cls, value: object) -> str:
        return safe_identifier(value, field="session_id")


class ExperienceResponse(ExperienceContractModel):
    session_id: str
    project_summary: str
    artifact_ids: tuple[str, ...] = ()
    file_count: int = Field(ge=0)
    message_count: int = Field(ge=0)
    progress_count: int = Field(ge=0)
    knowledge_traces: tuple[KnowledgeTrace, ...] = ()
    viewer_state: ViewerState

    @field_validator("session_id", mode="before")
    @classmethod
    def validate_session_id(cls, value: object) -> str:
        return safe_identifier(value, field="session_id")

    @field_validator("project_summary", mode="before")
    @classmethod
    def validate_project_summary(cls, value: object) -> str:
        return safe_summary(value, field="project_summary")

    @field_validator("artifact_ids", mode="before")
    @classmethod
    def validate_artifact_ids(cls, value: object) -> object:
        return _identifier_values(value, field="artifact_id")


class ReviewIntent(ExperienceContractModel):
    intent_id: str
    session_id: str
    artifact_id: str
    action: ReviewIntentAction
    source: Literal["user"] = "user"
    comment_summary: str | None = None
    timestamp: datetime

    @field_validator("intent_id", "session_id", "artifact_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return safe_identifier(value, field=info.field_name)

    @field_validator("comment_summary", mode="before")
    @classmethod
    def validate_comment_summary(cls, value: object) -> str | None:
        return safe_optional_summary(value, field="comment_summary")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: object) -> datetime:
        return utc_datetime(value, field="timestamp")


class ReviewReceipt(ExperienceContractModel):
    intent_id: str
    session_id: str
    artifact_id: str
    action: ReviewIntentAction
    source: Literal["user"] = "user"
    status: Literal[ReviewRecordStatus.RECORDED] = ReviewRecordStatus.RECORDED
    handoff: Literal["engineering_agent_review"] = "engineering_agent_review"
    recorded_at: datetime

    @field_validator("intent_id", "session_id", "artifact_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return safe_identifier(value, field=info.field_name)

    @field_validator("recorded_at")
    @classmethod
    def validate_recorded_at(cls, value: object) -> datetime:
        return utc_datetime(value, field="recorded_at")


class BlueprintNode(ExperienceContractModel):
    node_id: str
    label: str
    kind: str

    @field_validator("node_id", mode="before")
    @classmethod
    def validate_node_id(cls, value: object) -> str:
        return safe_identifier(value, field="node_id")

    @field_validator("label", "kind", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_summary(value, field=info.field_name, max_length=256)


class BlueprintEdge(ExperienceContractModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    label: str

    @field_validator(
        "edge_id",
        "source_node_id",
        "target_node_id",
        mode="before",
    )
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return safe_identifier(value, field=info.field_name)

    @field_validator("label", mode="before")
    @classmethod
    def validate_label(cls, value: object) -> str:
        return safe_summary(value, field="label", max_length=256)


class BlueprintProjection(ExperienceContractModel):
    session_id: str
    artifact_id: str
    nodes: tuple[BlueprintNode, ...] = ()
    edges: tuple[BlueprintEdge, ...] = ()

    @field_validator("session_id", "artifact_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return safe_identifier(value, field=info.field_name)

    @field_validator("nodes", "edges", mode="before")
    @classmethod
    def isolate_collections(cls, value: object) -> object:
        if isinstance(value, Sequence) and not isinstance(
            value,
            (str, bytes, bytearray),
        ):
            return tuple(copy.deepcopy(value))
        return value

    @model_validator(mode="after")
    def validate_graph_bindings(self) -> "BlueprintProjection":
        node_ids = tuple(item.node_id.casefold() for item in self.nodes)
        edge_ids = tuple(item.edge_id.casefold() for item in self.edges)
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("blueprint node identifiers are ambiguous")
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("blueprint edge identifiers are ambiguous")
        available = set(node_ids)
        if any(
            edge.source_node_id.casefold() not in available
            or edge.target_node_id.casefold() not in available
            for edge in self.edges
        ):
            raise ValueError("blueprint edge endpoints are unresolved")
        return self


def _identifier_values(value: object, *, field: str) -> object:
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
