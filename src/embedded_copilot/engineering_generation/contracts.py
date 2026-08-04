from __future__ import annotations

import copy
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from embedded_copilot.engineering_intelligence import (
    EngineeringContextSnapshot,
    EngineeringRecommendation,
)

from .models import (
    canonical_fingerprint,
    filename,
    fingerprint,
    identifier,
    safe_text,
    tuple_only,
)


class GenerationContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class GenerationType(StrEnum):
    FIRMWARE = "FIRMWARE"
    HARDWARE = "HARDWARE"
    INTERFACE = "INTERFACE"
    BOM = "BOM"


class ArtifactType(StrEnum):
    FIRMWARE = "FIRMWARE"
    HARDWARE = "HARDWARE"


class GenerationStatus(StrEnum):
    PROPOSED = "PROPOSED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    READY = "READY"


class DatasheetTrustStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PROJECTED = "PROJECTED"
    UNVERIFIED = "UNVERIFIED"


class GenerationRequest(GenerationContract):
    project_id: str
    generation_type: GenerationType
    context_snapshot: EngineeringContextSnapshot
    recommendation: EngineeringRecommendation

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project_id(cls, value: object) -> str:
        return identifier(value, field="project_id")

    @model_validator(mode="after")
    def bind_inputs(self) -> "GenerationRequest":
        if self.project_id != self.context_snapshot.project_id:
            raise ValueError("generation project does not match context")
        return self


class SystemArchitecture(GenerationContract):
    system: str
    components: tuple[str, ...]
    constraints: tuple[str, ...]

    @field_validator("system", mode="before")
    @classmethod
    def validate_system(cls, value: object) -> str:
        return safe_text(value, field="system")

    @field_validator("components", "constraints", mode="before")
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        return tuple_only(value, field=info.field_name)

    @field_validator("components", "constraints")
    @classmethod
    def validate_texts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(safe_text(item, field="architecture item") for item in value)


class InterfaceContract(GenerationContract):
    name: str
    protocol: str
    endpoints: tuple[str, ...]
    notes: str
    status: DatasheetTrustStatus

    @field_validator("name", "protocol", "notes", mode="before")
    @classmethod
    def validate_texts(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("endpoints", mode="before")
    @classmethod
    def validate_endpoints(cls, value: object) -> object:
        return tuple_only(value, field="endpoints")

    @field_validator("endpoints")
    @classmethod
    def validate_endpoint_texts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(safe_text(item, field="endpoint") for item in value)


class BOMProposal(GenerationContract):
    component: str
    reason: str
    risk: str
    alternative: str | None
    status: DatasheetTrustStatus

    @field_validator("component", "reason", "risk", mode="before")
    @classmethod
    def validate_texts(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("alternative", mode="before")
    @classmethod
    def validate_alternative(cls, value: object) -> str | None:
        return None if value is None else safe_text(value, field="alternative")


class ArtifactReference(GenerationContract):
    reference_id: str
    status: DatasheetTrustStatus

    @field_validator("reference_id", mode="before")
    @classmethod
    def validate_reference_id(cls, value: object) -> str:
        return identifier(value, field="reference_id")


class FirmwareArtifact(GenerationContract):
    artifact_id: str
    project_id: str
    artifact_type: Literal[ArtifactType.FIRMWARE] = ArtifactType.FIRMWARE
    files: tuple[str, ...]
    configuration: tuple[str, ...]
    dependencies: tuple[str, ...]
    summary: str
    fingerprint: str

    @field_validator("artifact_id", "project_id", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("files", "configuration", "dependencies", mode="before")
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        return tuple_only(value, field=info.field_name)

    @field_validator("files")
    @classmethod
    def validate_files(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(filename(item) for item in value)
        if len(checked) != len(set(checked)):
            raise ValueError("files must be unique")
        return checked

    @field_validator("configuration", "dependencies")
    @classmethod
    def validate_items(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(safe_text(item, field="proposal item") for item in value)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="summary")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "FirmwareArtifact":
        expected = canonical_fingerprint(self, exclude={"fingerprint"})
        if self.fingerprint != expected:
            raise ValueError("firmware artifact fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "FirmwareArtifact":
        provisional = cls.model_construct(
            **{
                **values,
                "artifact_type": ArtifactType.FIRMWARE,
                "fingerprint": "sha256:" + "0" * 64,
            }
        )
        values["artifact_type"] = ArtifactType.FIRMWARE
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class HardwareDesignArtifact(GenerationContract):
    artifact_id: str
    project_id: str
    artifact_type: Literal[ArtifactType.HARDWARE] = ArtifactType.HARDWARE
    system_architecture: SystemArchitecture
    interface_contracts: tuple[InterfaceContract, ...]
    bom: tuple[BOMProposal, ...]
    references: tuple[ArtifactReference, ...]
    summary: str
    fingerprint: str

    @field_validator("artifact_id", "project_id", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("interface_contracts", "bom", "references", mode="before")
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        return tuple_only(value, field=info.field_name)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="summary")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "HardwareDesignArtifact":
        expected = canonical_fingerprint(self, exclude={"fingerprint"})
        if self.fingerprint != expected:
            raise ValueError("hardware artifact fingerprint mismatch")
        return self

    @property
    def interfaces(self) -> tuple[InterfaceContract, ...]:
        return self.interface_contracts

    @classmethod
    def create(cls, **values: object) -> "HardwareDesignArtifact":
        provisional = cls.model_construct(
            **{
                **values,
                "artifact_type": ArtifactType.HARDWARE,
                "fingerprint": "sha256:" + "0" * 64,
            }
        )
        values["artifact_type"] = ArtifactType.HARDWARE
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


GenerationArtifact = FirmwareArtifact | HardwareDesignArtifact


class GenerationSnapshot(GenerationContract):
    project_id: str
    status: GenerationStatus
    artifacts: tuple[GenerationArtifact, ...]
    fingerprint: str

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project_id(cls, value: object) -> str:
        return identifier(value, field="project_id")

    @field_validator("artifacts", mode="before")
    @classmethod
    def validate_artifacts(cls, value: object) -> object:
        return tuple_only(value, field="artifacts")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify_snapshot(self) -> "GenerationSnapshot":
        ids = tuple(item.artifact_id for item in self.artifacts)
        projects = tuple(item.project_id for item in self.artifacts)
        if len(ids) != len(set(ids)) or any(
            project != self.project_id for project in projects
        ):
            raise ValueError("generation artifact identity is invalid")
        expected = canonical_fingerprint(self, exclude={"fingerprint"})
        if self.fingerprint != expected:
            raise ValueError("generation snapshot fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "GenerationSnapshot":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class GenerationPort(Protocol):
    def get_snapshot(self, project_id: str) -> GenerationSnapshot | None: ...


def validate_generation_snapshot(value: object) -> GenerationSnapshot:
    if not isinstance(value, GenerationSnapshot):
        raise TypeError("generation snapshot must be typed")
    return GenerationSnapshot.model_validate(copy.deepcopy(value))


__all__ = [
    "ArtifactReference",
    "ArtifactType",
    "BOMProposal",
    "DatasheetTrustStatus",
    "FirmwareArtifact",
    "GenerationArtifact",
    "GenerationContract",
    "GenerationPort",
    "GenerationRequest",
    "GenerationSnapshot",
    "GenerationStatus",
    "GenerationType",
    "HardwareDesignArtifact",
    "InterfaceContract",
    "SystemArchitecture",
    "validate_generation_snapshot",
]
