from __future__ import annotations

import copy
from collections.abc import Sequence

from pydantic import BaseModel

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.debug.analyzer import DebugAnalyzer, DebugRequirementAnalyzer
from embedded_copilot.debug.knowledge import (
    DebugKnowledgeRetriever,
    debug_evidence_provenance,
)
from embedded_copilot.debug.models import (
    DebugEvidence,
    DebugFinding,
    DebugPlan,
    DebugReport,
    DebugRequest,
    DebugValidationResult,
)
from embedded_copilot.debug.planner import DebugPlanner
from embedded_copilot.debug.validator import DebugValidator


_STAGE_FAILURES = {
    "requirement_analysis": (
        "debug requirement analysis failed",
        "DebugAnalysisError",
    ),
    "knowledge_retrieval": (
        "debug knowledge retrieval failed",
        "DebugKnowledgeError",
    ),
    "finding_analysis": ("debug finding analysis failed", "DebugAnalysisError"),
    "planning": ("debug planning failed", "DebugPlanningError"),
    "report_assembly": ("debug report assembly failed", "DebugPlanningError"),
    "validation": ("debug report validation failed", "DebugValidationError"),
}


class DebugAgent(BaseAgent):
    """Synchronous deterministic Debug Intelligence orchestrator."""

    name = "DebugAgent"
    description = "Produces bounded, offline deterministic debug reports."
    capabilities = (
        "error_analysis",
        "root_cause_analysis",
        "debug_planning",
    )

    def __init__(
        self,
        requirement_analyzer: DebugRequirementAnalyzer | None = None,
        retriever: DebugKnowledgeRetriever | None = None,
        debug_analyzer: DebugAnalyzer | None = None,
        planner: DebugPlanner | None = None,
        validator: DebugValidator | None = None,
    ) -> None:
        self._requirement_analyzer = (
            requirement_analyzer
            if requirement_analyzer is not None
            else DebugRequirementAnalyzer()
        )
        self._retriever = (
            retriever if retriever is not None else DebugKnowledgeRetriever()
        )
        self._debug_analyzer = (
            debug_analyzer if debug_analyzer is not None else DebugAnalyzer()
        )
        self._planner = planner if planner is not None else DebugPlanner()
        self._validator = validator if validator is not None else DebugValidator()

    def run(self, task: AgentTask) -> AgentResult:
        try:
            raw_request = self._requirement_analyzer.analyze(
                task.requirement,
                metadata=copy.deepcopy(task.metadata),
            )
            request = _revalidate(DebugRequest, raw_request)
        except Exception:
            return self._failure("requirement_analysis")

        try:
            raw_documents = self._retriever.retrieve(
                _revalidate(DebugRequest, request)
            )
            documents = _revalidate_sequence(DebugEvidence, raw_documents)
            document_provenance = [
                copy.deepcopy(debug_evidence_provenance(document))
                for document in documents
            ]
        except Exception:
            return self._failure("knowledge_retrieval")

        try:
            raw_findings = self._debug_analyzer.analyze(
                _revalidate(DebugRequest, request),
                _revalidate_sequence(DebugEvidence, documents),
            )
            findings = _revalidate_sequence(DebugFinding, raw_findings)
        except Exception:
            return self._failure("finding_analysis")

        try:
            raw_plan = self._planner.plan(
                _revalidate(DebugRequest, request),
                _revalidate_sequence(DebugFinding, findings),
                _revalidate_sequence(DebugEvidence, documents),
            )
            plan = _revalidate(DebugPlan, raw_plan)
        except Exception:
            return self._failure("planning")

        try:
            report = _assemble_report(plan)
            report = _revalidate(DebugReport, report)
            report_output = report.model_dump_json()
            report_metadata = copy.deepcopy(report.model_dump(mode="json"))
        except Exception:
            return self._failure("report_assembly")

        try:
            raw_validation = self._validator.validate(
                _revalidate(DebugReport, report)
            )
            validation = _revalidate(DebugValidationResult, raw_validation)
            if not validation.success:
                return self._failure("validation")
            validation_metadata = copy.deepcopy(
                validation.model_dump(mode="json")
            )
        except Exception:
            return self._failure("validation")

        try:
            result = AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                output=report_output,
                metadata={
                    "debug_report": report_metadata,
                    "retrieved_documents": document_provenance,
                    "validation": validation_metadata,
                },
            )
            result.model_dump_json()
            return result
        except Exception:
            return self._failure("report_assembly")

    def _failure(self, stage: str) -> AgentResult:
        output, error_type = _STAGE_FAILURES[stage]
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.ERROR,
            output=output,
            metadata={"stage": stage, "error_type": error_type},
        )


def _model_payload(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python")
    return value


def _revalidate(model_type: type[BaseModel], value: object):
    return model_type.model_validate(copy.deepcopy(_model_payload(value)))


def _revalidate_sequence(model_type: type[BaseModel], value: object) -> list:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("pipeline stage must return a sequence")
    return [_revalidate(model_type, item) for item in value]


def _assemble_report(plan: DebugPlan) -> DebugReport:
    recommendations: list[str] = []
    seen: set[str] = set()
    for recommendation in [
        *(finding.recommendation for finding in plan.findings),
        *plan.actions,
    ]:
        key = recommendation.casefold()
        if key not in seen:
            seen.add(key)
            recommendations.append(recommendation)
    platform = plan.platform or "unspecified platform"
    return DebugReport(
        project_name=plan.project_name,
        platform=plan.platform,
        error_type=plan.error_type,
        summary=(
            f"Debug analysis produced {len(plan.findings)} finding(s) for "
            f"{platform} {plan.error_type}; results are offline engineering "
            "guidance and are not hardware-verified."
        ),
        findings=copy.deepcopy(plan.findings),
        recommendations=recommendations,
        metadata=copy.deepcopy(plan.metadata),
    )
