from __future__ import annotations

import copy
from collections.abc import Mapping

from pydantic import field_validator

from embedded_copilot.agents.types import AgentTask
from embedded_copilot.pcb.exceptions import PCBAnalysisError
from embedded_copilot.pcb.models import (
    PCBIssue,
    PCBRequirement,
    PCBRuleEvaluation,
    PCBStructureEvidence,
    UnifiedPCBModel,
)
from embedded_copilot.pcb.structure_rules import PCBStructureRuleEngine
from embedded_copilot.schemas.result import ContractModel


_PCB_MODEL_CONTEXT_KEY = "_pcb_model_context"


class _PCBModelEnvelope(ContractModel):
    pcb_model: UnifiedPCBModel

    @field_validator("pcb_model", mode="before")
    @classmethod
    def isolate_model(cls, value: object) -> object:
        return copy.deepcopy(value)


def _copy_model(model: UnifiedPCBModel) -> UnifiedPCBModel:
    return UnifiedPCBModel.model_validate(
        copy.deepcopy(model.model_dump(mode="python"))
    )


def attach_pcb_model(task: AgentTask, pcb_model: UnifiedPCBModel) -> AgentTask:
    if not isinstance(task, AgentTask) or not isinstance(
        pcb_model, UnifiedPCBModel
    ):
        raise PCBAnalysisError("PCB analysis adapter is invalid")
    try:
        payload = copy.deepcopy(task.model_dump(mode="python"))
        metadata = payload["metadata"]
        if not isinstance(metadata, dict):
            raise TypeError("invalid task metadata")
        if _PCB_MODEL_CONTEXT_KEY in metadata:
            raise PCBAnalysisError("PCB model context already exists")
        metadata[_PCB_MODEL_CONTEXT_KEY] = _PCBModelEnvelope(
            pcb_model=_copy_model(pcb_model)
        )
        return AgentTask.model_validate(payload)
    except PCBAnalysisError:
        raise
    except Exception:
        raise PCBAnalysisError("PCB analysis adapter is invalid") from None


def _consume_pcb_model(
    metadata: Mapping[str, object] | None,
) -> tuple[dict[str, object], UnifiedPCBModel | None]:
    try:
        copied = copy.deepcopy(dict(metadata or {}))
        raw_context = copied.pop(_PCB_MODEL_CONTEXT_KEY, None)
        if raw_context is None:
            return copied, None
        if not isinstance(raw_context, _PCBModelEnvelope):
            raise TypeError("invalid PCB model envelope")
        return copied, _copy_model(raw_context.pcb_model)
    except Exception:
        raise PCBAnalysisError("PCB model context is invalid") from None


def adapt_pcb_model(
    model: UnifiedPCBModel,
) -> tuple[PCBRequirement, PCBRuleEvaluation]:
    if not isinstance(model, UnifiedPCBModel):
        raise PCBAnalysisError("PCB structure analysis failed")
    try:
        component_values = [
            component.value or component.footprint for component in model.components
        ]
        searchable = " ".join(component_values).casefold()
        platform = (
            "ESP32"
            if "esp32" in searchable
            else "STM32" if "stm32" in searchable else None
        )
        requirement = PCBRequirement(
            project_name=model.board_name,
            platform=platform,
            components=component_values,
            interfaces=[],
            constraints=[],
        )
        evidence = PCBStructureRuleEngine().evaluate(model)
        evaluation = _evidence_to_evaluation(evidence)
        return requirement, evaluation
    except Exception:
        raise PCBAnalysisError("PCB structure analysis failed") from None


def _evidence_to_evaluation(
    evidence: tuple[PCBStructureEvidence, ...],
) -> PCBRuleEvaluation:
    issues: list[PCBIssue] = []
    passed: list[str] = []
    for item in evidence:
        if item.outcome in {"present", "connected"}:
            passed.append(item.rule_id)
            continue
        if item.rule_id == "pcb-structure-power-net":
            description = "No power net was identified in the parsed PCB structure."
            recommendation = "Verify power-net naming and connectivity in the EDA tool."
        elif item.rule_id == "pcb-structure-ground-net":
            description = "No ground net was identified in the parsed PCB structure."
            recommendation = "Verify ground-net naming and connectivity in the EDA tool."
        elif item.rule_id == "pcb-structure-floating-pins":
            if item.outcome == "missing":
                description = (
                    "Connectivity could not be evaluated because no electrical "
                    "pads were parsed."
                )
                recommendation = (
                    "Verify that the board contains supported electrical pads in "
                    "the EDA tool."
                )
            else:
                description = "Electrical pads without assigned nets were identified."
                recommendation = (
                    "Review the listed pads in the EDA tool and confirm intent."
                )
        else:
            raise ValueError("unsupported PCB structure evidence")
        issues.append(
            PCBIssue(
                id=item.rule_id,
                category=item.category,
                severity="warning",
                description=description,
                recommendation=recommendation,
                evidence=list(item.evidence),
                metadata={"evidence_source": "parsed_pcb_structure"},
            )
        )
    return PCBRuleEvaluation(issues=issues, passed_rules=passed)
