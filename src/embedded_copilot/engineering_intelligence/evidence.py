from __future__ import annotations

import copy

from pydantic import ValidationError

from .contracts import EvidenceClaim, EngineeringEvidence, canonical_fingerprint


def build_evidence(**values: object) -> EngineeringEvidence:
    if isinstance(values.get("claim"), dict):
        values = {**values, "claim": EvidenceClaim.model_validate(values["claim"])}
    material = EngineeringEvidence.model_construct(
        **values,
        fingerprint="sha256:" + "0" * 64,
    )
    return EngineeringEvidence.model_validate(
        {
            **material.model_dump(mode="python"),
            "fingerprint": canonical_fingerprint(material, exclude={"fingerprint"}),
        }
    )


def validate_evidence(value: EngineeringEvidence) -> EngineeringEvidence:
    if type(value) is not EngineeringEvidence:
        raise TypeError("evidence must be a typed projection")
    try:
        return EngineeringEvidence.model_validate(copy.deepcopy(value))
    except (TypeError, ValidationError) as error:
        raise ValueError("evidence is invalid") from error
