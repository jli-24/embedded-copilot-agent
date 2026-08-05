from __future__ import annotations

import copy
import re
from typing import Protocol, runtime_checkable

from pydantic import field_validator, model_validator

from .models import (
    ComponentProjection,
    DesignSourceType,
    HardwareCapabilitySnapshot,
    InterfaceProjection,
    LayerProjection,
    NetProjection,
    ProjectionStatus,
    UnifiedHardwareModel,
    V22Contract,
    _v22_canonical,
    _v22_fingerprint,
    _v22_id,
    _v22_text,
)

_SOURCE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")


class HardwareSourceReference(V22Contract):
    project_id: str
    design_id: str
    filename: str
    source_type: DesignSourceType
    fingerprint: str

    @field_validator("project_id", "design_id", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return _v22_id(value, field=info.field_name)

    @field_validator("filename", mode="before")
    @classmethod
    def validate_filename(cls, value: object) -> str:
        candidate = _v22_text(value, field="filename", maximum=160)
        if not _SOURCE_FILENAME.fullmatch(
            candidate
        ) or not candidate.casefold().endswith(
            (".kicad_pro", ".kicad_sch", ".kicad_pcb")
        ):
            raise ValueError("KiCad filename is invalid")
        return candidate

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_reference_fingerprint(cls, value: object) -> str:
        return _v22_fingerprint(value)

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "HardwareSourceReference":
        if self.fingerprint != _v22_canonical(self, exclude={"fingerprint"}):
            raise ValueError("hardware source reference fingerprint mismatch")
        if self.source_type is not DesignSourceType.KICAD:
            raise ValueError("KiCad source reference must use KICAD source type")
        return self

    @classmethod
    def create(cls, **values: object) -> "HardwareSourceReference":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = _v22_canonical(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


@runtime_checkable
class KiCadParserPort(Protocol):
    def parse(self, source: HardwareSourceReference) -> UnifiedHardwareModel: ...


@runtime_checkable
class HardwareDesignPort(Protocol):
    def get_snapshot(self, project_id: str) -> UnifiedHardwareModel | None: ...


def validate_unified_hardware_model(value: object) -> UnifiedHardwareModel:
    if type(value) is not UnifiedHardwareModel:
        raise TypeError("unified hardware model is invalid")
    return UnifiedHardwareModel.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


def validate_hardware_capability_snapshot(
    value: object,
) -> HardwareCapabilitySnapshot:
    if type(value) is not HardwareCapabilitySnapshot:
        raise TypeError("hardware capability snapshot is invalid")
    return HardwareCapabilitySnapshot.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


__all__ = [
    "ComponentProjection",
    "DesignSourceType",
    "HardwareCapabilitySnapshot",
    "HardwareDesignPort",
    "HardwareSourceReference",
    "InterfaceProjection",
    "KiCadParserPort",
    "LayerProjection",
    "NetProjection",
    "ProjectionStatus",
    "UnifiedHardwareModel",
    "validate_hardware_capability_snapshot",
    "validate_unified_hardware_model",
]
