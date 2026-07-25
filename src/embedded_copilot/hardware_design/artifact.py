from __future__ import annotations

from typing import Literal

from pydantic import field_validator, model_validator

from embedded_copilot.hardware_design._validation import (
    HardwareDesignModel,
    tuple_values,
)
from embedded_copilot.hardware_design.approval import DesignApproval
from embedded_copilot.hardware_design.decision import DesignDecision
from embedded_copilot.hardware_design.evidence import DesignEvidence
from embedded_copilot.hardware_design.models import HardwareDesignBlueprint


class HardwareDesignArtifact(HardwareDesignModel):
    schema_version: Literal[1] = 1
    blueprint: HardwareDesignBlueprint
    evidence: tuple[DesignEvidence, ...] = ()
    decisions: tuple[DesignDecision, ...] = ()
    approval: DesignApproval

    @field_validator("evidence", "decisions", mode="before")
    @classmethod
    def isolate_collections(cls, value: object) -> object:
        return tuple_values(value)

    @model_validator(mode="after")
    def validate_bindings(self) -> "HardwareDesignArtifact":
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("hardware design evidence identifiers are ambiguous")
        decision_ids = [item.decision_id for item in self.decisions]
        if len(decision_ids) != len(set(decision_ids)):
            raise ValueError("hardware design decision identifiers are ambiguous")
        available_evidence = set(evidence_ids)
        if any(
            not set(decision.evidence_ids).issubset(available_evidence)
            for decision in self.decisions
        ):
            raise ValueError("hardware design decision evidence is unresolved")

        evidence_sources = {item.source_id for item in self.evidence}
        if set(self.blueprint.source_ids) != evidence_sources:
            raise ValueError("hardware design blueprint evidence is unresolved")

        nested_sources = {
            source_id
            for values in (
                *(item.source_ids for item in self.blueprint.modules),
                *(item.source_ids for item in self.blueprint.components),
                *(item.source_ids for item in self.blueprint.connections),
                *(item.source_ids for item in self.blueprint.gpio_assignments),
                self.blueprint.power_tree.source_ids,
                tuple(item.source_id for item in self.evidence),
            )
            for source_id in values
        }
        if not nested_sources.issubset(set(self.blueprint.source_ids)):
            raise ValueError("hardware design source evidence is unresolved")
        return self
