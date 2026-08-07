from __future__ import annotations

import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .models import (
    canonical_fingerprint,
    fingerprint,
    identifier,
    safe_text,
    tuple_only,
)


class CompletionContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class EngineeringConfidence(StrEnum):
    VERIFIED = "VERIFIED"
    PROJECTED = "PROJECTED"
    UNVERIFIED = "UNVERIFIED"


class EngineeringReviewCategory(StrEnum):
    HARDWARE = "HARDWARE"
    FIRMWARE = "FIRMWARE"
    INTERFACE = "INTERFACE"
    VALIDATION = "VALIDATION"


class EngineeringReviewStatus(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    UNVERIFIED = "UNVERIFIED"


class ValidationStatus(StrEnum):
    VALID = "VALID"
    REJECTED = "REJECTED"
    UNAVAILABLE = "UNAVAILABLE"


class ValidationReason(StrEnum):
    PROJECT_MISMATCH = "PROJECT_MISMATCH"
    FINGERPRINT_MISMATCH = "FINGERPRINT_MISMATCH"
    INVALID_REFERENCE = "INVALID_REFERENCE"
    CONTEXT_MISMATCH = "CONTEXT_MISMATCH"
    PORT_UNAVAILABLE = "PORT_UNAVAILABLE"


class EngineeringRequirementProjection(CompletionContract):
    project_id: str
    title: str
    description: str
    functional_requirements: tuple[str, ...] = Field(max_length=128)
    non_functional_requirements: tuple[str, ...] = Field(max_length=128)
    constraints: tuple[str, ...] = Field(max_length=128)
    interfaces: tuple[str, ...] = Field(max_length=128)
    confidence: EngineeringConfidence
    fingerprint: str

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project(cls, value: object) -> str:
        return identifier(value, field="project_id")

    @field_validator("title", "description", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator(
        "functional_requirements",
        "non_functional_requirements",
        "constraints",
        "interfaces",
        mode="before",
    )
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        return tuple_only(value, field=info.field_name)

    @field_validator(
        "functional_requirements",
        "non_functional_requirements",
        "constraints",
        "interfaces",
    )
    @classmethod
    def validate_items(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(safe_text(item, field="requirement") for item in value)
        if len(checked) != len(set(checked)):
            raise ValueError("requirements must be unique")
        return checked

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> EngineeringRequirementProjection:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("requirement fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> EngineeringRequirementProjection:
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class EngineeringArchitectureSnapshot(CompletionContract):
    project_id: str
    components: tuple[str, ...] = Field(max_length=128)
    interfaces: tuple[str, ...] = Field(max_length=128)
    constraints: tuple[str, ...] = Field(max_length=128)
    decision_references: tuple[str, ...] = Field(max_length=128)
    confidence: EngineeringConfidence
    fingerprint: str

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project(cls, value: object) -> str:
        return identifier(value, field="project_id")

    @field_validator(
        "components", "interfaces", "constraints", "decision_references", mode="before"
    )
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        return tuple_only(value, field=info.field_name)

    @field_validator("components", "interfaces", "constraints", "decision_references")
    @classmethod
    def validate_items(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(
            identifier(item, field="architecture_reference")
            if "reference" in item.casefold()
            else safe_text(item, field="architecture_item")
            for item in value
        )
        if len(checked) != len(set(checked)):
            raise ValueError("architecture items must be unique")
        return checked

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> EngineeringArchitectureSnapshot:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("architecture fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> EngineeringArchitectureSnapshot:
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class EngineeringInterfaceContract(CompletionContract):
    interface_id: str
    project_id: str
    producer: str
    consumer: str
    protocol: str
    data_reference: str
    constraints: tuple[str, ...] = Field(max_length=64)
    fingerprint: str

    @field_validator("interface_id", "project_id", "data_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("producer", "consumer", "protocol", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name, maximum=160)

    @field_validator("constraints", mode="before")
    @classmethod
    def validate_constraints(cls, value: object) -> object:
        return tuple_only(value, field="constraints")

    @field_validator("constraints")
    @classmethod
    def validate_constraint_items(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(safe_text(item, field="constraint") for item in value)
        if len(checked) != len(set(checked)):
            raise ValueError("interface constraints must be unique")
        return checked

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> EngineeringInterfaceContract:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("interface fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> EngineeringInterfaceContract:
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class EngineeringReviewSnapshot(CompletionContract):
    review_id: str
    project_id: str
    category: EngineeringReviewCategory
    status: EngineeringReviewStatus
    finding_reference: str
    confidence: EngineeringConfidence
    fingerprint: str

    @field_validator("review_id", "project_id", "finding_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> EngineeringReviewSnapshot:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("review fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> EngineeringReviewSnapshot:
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class EngineeringCompletionSnapshot(CompletionContract):
    project_id: str
    requirement: EngineeringRequirementProjection
    architecture: EngineeringArchitectureSnapshot
    interfaces: tuple[EngineeringInterfaceContract, ...] = Field(max_length=128)
    reviews: tuple[EngineeringReviewSnapshot, ...] = Field(max_length=128)
    fingerprint: str

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project(cls, value: object) -> str:
        return identifier(value, field="project_id")

    @field_validator("interfaces", "reviews", mode="before")
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        return tuple_only(value, field=info.field_name)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> EngineeringCompletionSnapshot:
        if self.requirement.project_id != self.project_id:
            raise ValueError("requirement project binding mismatch")
        if self.architecture.project_id != self.project_id:
            raise ValueError("architecture project binding mismatch")
        if any(item.project_id != self.project_id for item in self.interfaces):
            raise ValueError("interface project binding mismatch")
        if any(item.project_id != self.project_id for item in self.reviews):
            raise ValueError("review project binding mismatch")
        interface_ids = tuple(item.interface_id for item in self.interfaces)
        review_ids = tuple(item.review_id for item in self.reviews)
        if len(interface_ids) != len(set(interface_ids)):
            raise ValueError("interface ids must be unique")
        if len(review_ids) != len(set(review_ids)):
            raise ValueError("review ids must be unique")
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("completion fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> EngineeringCompletionSnapshot:
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class ValidationResult(CompletionContract):
    project_id: str
    snapshot_fingerprint: str
    context_fingerprint: str
    status: ValidationStatus
    summary: str
    fingerprint: str
    reason: ValidationReason | None = Field(default=None, exclude=True)

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project(cls, value: object) -> str:
        return identifier(value, field="project_id")

    @field_validator("snapshot_fingerprint", "context_fingerprint", mode="before")
    @classmethod
    def validate_fingerprints(cls, value: object, info) -> str:
        return fingerprint(value, field=info.field_name)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="summary")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> ValidationResult:
        if self.fingerprint != canonical_fingerprint(
            self, exclude={"fingerprint", "reason"}
        ):
            raise ValueError("validation result fingerprint mismatch")
        if self.status is ValidationStatus.VALID and self.reason is not None:
            raise ValueError("valid result cannot contain a rejection reason")
        if self.status is ValidationStatus.REJECTED and self.reason is None:
            raise ValueError("rejected result requires a reason")
        return self

    @classmethod
    def create(cls, **values: object) -> ValidationResult:
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint", "reason"}
        )
        return cls.model_validate(values)


@runtime_checkable
class EngineeringCompletionPort(Protocol):
    def get_snapshot(self, project_id: str) -> EngineeringCompletionSnapshot | None: ...


def validate_completion_snapshot(value: object) -> EngineeringCompletionSnapshot:
    if type(value) is not EngineeringCompletionSnapshot:
        raise TypeError("completion snapshot is invalid")
    return EngineeringCompletionSnapshot.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


def validate_validation_result(value: object) -> ValidationResult:
    if type(value) is not ValidationResult:
        raise TypeError("validation result is invalid")
    return ValidationResult.model_validate(
        copy.deepcopy(value.model_dump(mode="python", exclude_none=False))
    )


__all__ = [
    "CompletionContract",
    "EngineeringArchitectureSnapshot",
    "EngineeringCompletionPort",
    "EngineeringCompletionSnapshot",
    "EngineeringConfidence",
    "EngineeringInterfaceContract",
    "EngineeringRequirementProjection",
    "EngineeringReviewCategory",
    "EngineeringReviewSnapshot",
    "EngineeringReviewStatus",
    "ValidationReason",
    "ValidationResult",
    "ValidationStatus",
    "validate_completion_snapshot",
    "validate_validation_result",
]
