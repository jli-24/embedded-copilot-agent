from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .models import EngineeringDecisionMemory, EngineeringMemorySnapshot

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,127}$")
_FP = re.compile(r"^sha256:[a-f0-9]{64}$")


class ApprovedMemoryProjection(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )

    project_id: str
    memory_id: str
    record_id: str
    memory_type: str
    status: Literal["APPROVED"]
    source_reference: str
    source_revision: str
    title: str
    summary: str
    evidence_references: tuple[str, ...] = ()
    fingerprint: str

    @field_validator(
        "project_id", "memory_id", "record_id", "source_reference", "source_revision",
        mode="before",
    )
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{info.field_name} is invalid")
        checked = unicodedata.normalize("NFC", value).strip()
        if not _ID.fullmatch(checked):
            raise ValueError(f"{info.field_name} is invalid")
        return checked

    @field_validator("title", "summary", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{info.field_name} is invalid")
        checked = unicodedata.normalize("NFC", value).strip()
        if not checked or "\x00" in checked or "\n" in checked or "\r" in checked:
            raise ValueError(f"{info.field_name} is invalid")
        return checked

    @field_validator("evidence_references", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> object:
        if not isinstance(value, tuple):
            raise ValueError("evidence_references must be a tuple")
        return copy.deepcopy(value)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        if not isinstance(value, str) or not _FP.fullmatch(value):
            raise ValueError("fingerprint is invalid")
        return value

    @model_validator(mode="after")
    def validate_bound_fingerprint(self) -> ApprovedMemoryProjection:
        data = self.model_dump(mode="json", exclude={"fingerprint"})
        encoded = json.dumps(
            data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        expected = "sha256:" + hashlib.sha256(encoded).hexdigest()
        if self.fingerprint != expected:
            raise ValueError("approved projection fingerprint mismatch")
        return self


def projection_from_snapshot(
    snapshot: EngineeringMemorySnapshot, *, record_id: str
) -> ApprovedMemoryProjection:
    if snapshot.snapshot_type.value != "VERIFIED":
        raise ValueError("only verified memory can be projected")
    record = next((item for item in snapshot.records if item.record_id == record_id), None)
    if record is None or record.status.value != "VERIFIED":
        raise ValueError("approved memory record was not found")
    payload = record.payload
    if not isinstance(payload, EngineeringDecisionMemory):
        raise ValueError("memory payload is not projectable")
    title = "Engineering Decision"
    summary = f"{payload.decision} Rationale: {payload.rationale_summary}"
    material = {
        "project_id": snapshot.project_id,
        "memory_id": snapshot.memory_id,
        "record_id": record.record_id,
        "memory_type": payload.memory_type.value,
        "status": "APPROVED",
        "source_reference": record.provenance.source_reference,
        "source_revision": record.provenance.source_revision,
        "title": title,
        "summary": summary,
        "evidence_references": (record.provenance.source_reference,),
    }
    provisional = ApprovedMemoryProjection.model_construct(
        **material, fingerprint="sha256:" + "0" * 64
    )
    data = provisional.model_dump(mode="json", exclude={"fingerprint"})
    encoded = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return ApprovedMemoryProjection.model_validate(
        {**material, "fingerprint": "sha256:" + hashlib.sha256(encoded).hexdigest()}
    )


__all__ = ("ApprovedMemoryProjection", "projection_from_snapshot")
