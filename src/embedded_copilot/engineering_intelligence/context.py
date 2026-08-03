from __future__ import annotations

import copy
from typing import Protocol

from pydantic import ValidationError

from .contracts import (
    EngineeringContextInputProjection,
    EngineeringContextSnapshot,
    canonical_fingerprint,
)


class EngineeringContextPort(Protocol):
    def get_context(self, project_id: str) -> EngineeringContextInputProjection | None: ...


def build_context_snapshot(
    value: EngineeringContextInputProjection,
) -> EngineeringContextSnapshot:
    if type(value) is not EngineeringContextInputProjection:
        raise TypeError("context input must be a typed projection")
    checked = EngineeringContextInputProjection.model_validate(copy.deepcopy(value))
    material = EngineeringContextSnapshot.model_construct(
        schema_version="1.0",
        context_fingerprint="sha256:" + "0" * 64,
        project_id=checked.project_id,
        project_name=checked.project_name,
        stage=checked.stage,
        decision_topic=checked.decision_topic,
        constraints=checked.constraints,
        requirements=checked.requirements,
        feedback=checked.feedback,
        build_observations=checked.build_observations,
        memory_references=checked.memory_references,
        datasheet_references=checked.datasheet_references,
        events=checked.events,
    )
    return EngineeringContextSnapshot.model_validate(
        {
            **material.model_dump(mode="python"),
            "context_fingerprint": canonical_fingerprint(
                material, exclude={"context_fingerprint"}
            ),
        }
    )


def validate_context_snapshot(
    value: EngineeringContextSnapshot,
) -> EngineeringContextSnapshot:
    if type(value) is not EngineeringContextSnapshot:
        raise TypeError("context snapshot must be a typed projection")
    try:
        return EngineeringContextSnapshot.model_validate(copy.deepcopy(value))
    except (TypeError, ValidationError) as error:
        raise ValueError("context snapshot is unavailable") from error
