from __future__ import annotations

from collections.abc import Sequence

from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.pcb.analyzer import PCBRequirementAnalyzer
from embedded_copilot.pcb.knowledge.models import PCBRuleDocument
from embedded_copilot.pcb.models import (
    PCBRequirement,
    PCBReviewReport,
    PCBRuleEvaluation,
    UnifiedPCBModel,
)
from embedded_copilot.pcb.rules import PCBRuleEngine


class PCBReviewer:
    """Compose deterministic rule output and knowledge provenance into a report."""

    def __init__(
        self,
        *,
        analyzer: PCBRequirementAnalyzer | None = None,
        rule_engine: PCBRuleEngine | None = None,
    ) -> None:
        self._analyzer = analyzer if analyzer is not None else PCBRequirementAnalyzer()
        self._rule_engine = rule_engine if rule_engine is not None else PCBRuleEngine()

    def review(
        self,
        requirement: PCBRequirement,
        documents: Sequence[PCBRuleDocument],
        *,
        evaluation: PCBRuleEvaluation | None = None,
    ) -> PCBReviewReport:
        active_evaluation = (
            evaluation
            if evaluation is not None
            else self._rule_engine.evaluate(requirement)
        )
        warnings = ["PCB recommendations are deterministic and unverified."]
        if documents:
            references = ", ".join(
                f"{document.title} ({document.id})" for document in documents
            )
            summary = (
                "Deterministic PCB requirement review with retrieved knowledge provenance: "
                f"{references}. No EDA design was inspected."
            )
        else:
            summary = (
                "Deterministic PCB requirement review used no PCB knowledge documents; "
                "recommendations are generic and unverified."
            )
            warnings.append(
                "No PCB knowledge documents were retrieved; guidance is generic and unverified."
            )

        return PCBReviewReport(
            project_name=requirement.project_name,
            platform=requirement.platform,
            issues=list(active_evaluation.issues),
            passed_rules=list(active_evaluation.passed_rules),
            warnings=warnings,
            summary=summary,
            metadata={
                "review_mode": "deterministic_unverified",
                "evidence_document_ids": [document.id for document in documents],
                "rule_count": (
                    len(active_evaluation.issues)
                    + len(active_evaluation.passed_rules)
                ),
            },
        )

    def review_hardware_plan(self, plan: HardwarePlan) -> PCBReviewReport:
        requirement = self._analyzer.analyze(plan)
        return self.review(requirement, [])

    def review_structured(
        self,
        requirement: PCBRequirement,
        documents: Sequence[PCBRuleDocument],
        *,
        evaluation: PCBRuleEvaluation,
        pcb_model: UnifiedPCBModel,
    ) -> PCBReviewReport:
        """Compose a stable report from parsed structure evidence without DRC."""
        return PCBReviewReport(
            project_name=requirement.project_name,
            platform=requirement.platform,
            issues=list(evaluation.issues),
            passed_rules=list(evaluation.passed_rules),
            warnings=[
                "PCB structure analysis is deterministic and unverified.",
                "EDA connectivity, DRC, and electrical behavior require independent verification.",
            ],
            summary=(
                "Deterministic review of parsed KiCad PCB structure completed; "
                "DRC was not executed and the EDA file was not modified."
            ),
            metadata={
                "review_mode": "deterministic_structured",
                "source_format": pcb_model.source_format,
                "component_count": len(pcb_model.components),
                "net_count": len(pcb_model.nets),
                "evidence_document_ids": [document.id for document in documents],
                "rule_count": len(evaluation.issues) + len(evaluation.passed_rules),
            },
        )
