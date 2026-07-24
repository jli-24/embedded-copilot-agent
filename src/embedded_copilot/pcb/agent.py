from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.knowledge.injection import extract_centralized_knowledge
from embedded_copilot.pcb.adapters import adapt_pcb_model, _consume_pcb_model
from embedded_copilot.pcb.analyzer import PCBRequirementAnalyzer
from embedded_copilot.pcb.exceptions import (
    PCBAnalysisError,
    PCBIntelligenceError,
    PCBKnowledgeError,
    PCBReviewError,
    PCBRuleError,
    PCBValidationError,
)
from embedded_copilot.pcb.knowledge.models import PCBRuleDocument
from embedded_copilot.pcb.knowledge.retriever import PCBKnowledgeRetriever
from embedded_copilot.pcb.models import (
    PCBRequirement,
    PCBReviewReport,
    PCBRuleEvaluation,
    PCBValidationResult,
    UnifiedPCBModel,
)
from embedded_copilot.pcb.reviewer import PCBReviewer
from embedded_copilot.pcb.rules import PCBRuleEngine
from embedded_copilot.pcb.validator import PCBValidator


class PCBAgent(BaseAgent):
    """Synchronous deterministic PCB requirement review agent."""

    name = "PCBAgent"
    description = "Produces unverified, structured PCB requirement reviews."
    capabilities = ("pcb_review", "design_rule_analysis")

    def __init__(
        self,
        *,
        analyzer: PCBRequirementAnalyzer | None = None,
        retriever: PCBKnowledgeRetriever | None = None,
        rule_engine: PCBRuleEngine | None = None,
        reviewer: PCBReviewer | None = None,
        validator: PCBValidator | None = None,
    ) -> None:
        self._analyzer = analyzer if analyzer is not None else PCBRequirementAnalyzer()
        self._retriever = (
            retriever if retriever is not None else PCBKnowledgeRetriever()
        )
        self._rule_engine = rule_engine if rule_engine is not None else PCBRuleEngine()
        self._reviewer = reviewer if reviewer is not None else PCBReviewer()
        self._validator = validator if validator is not None else PCBValidator()

    def run(self, task: AgentTask) -> AgentResult:
        try:
            source, metadata = self._resolve_source(task)
            try:
                centralized = extract_centralized_knowledge(
                    metadata,
                    field="knowledge_documents",
                    model_type=PCBRuleDocument,
                )
            except Exception as exc:
                raise PCBKnowledgeError("PCB knowledge retrieval failed") from exc
            if centralized is not None:
                metadata = centralized[0]
            if isinstance(source, UnifiedPCBModel):
                requirement, evaluation = adapt_pcb_model(source)
            else:
                requirement = self._analyze(source, metadata)
                evaluation = self._evaluate_rules(requirement)
            if centralized is None:
                documents = self._retrieve_documents(_retrieval_query(requirement))
                retrieved_documents = [
                    _document_provenance(document) for document in documents
                ]
            else:
                documents = centralized[1]
                retrieved_documents = centralized[2]
            report = self._create_report(
                requirement,
                documents,
                evaluation,
                pcb_model=source if isinstance(source, UnifiedPCBModel) else None,
            )
            validation = self._validate_report(report)
            if not validation.success:
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.ERROR,
                    output="PCB review validation failed",
                    metadata={
                        "pcb_review": {
                            "status": "rejected",
                            "issue_count": len(report.issues),
                        },
                        "retrieved_documents": [],
                        "validation": {
                            "success": False,
                            "errors": ["PCB review validation failed"],
                            "warnings": [],
                            "metadata": {"error_count": len(validation.errors)},
                        },
                    },
                )

            report_payload = report.model_dump(mode="json")
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                output=report.model_dump_json(),
                metadata={
                    "pcb_review": report_payload,
                    "retrieved_documents": retrieved_documents,
                    "validation": validation.model_dump(mode="json"),
                },
            )
        except PCBIntelligenceError as exc:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                output=self._safe_error_message(exc),
                metadata={"error_type": type(exc).__name__},
            )
        except (ValidationError, ValueError) as exc:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                output="PCB request validation failed",
                metadata={"error_type": type(exc).__name__},
            )

    @staticmethod
    def _resolve_source(
        task: AgentTask,
    ) -> tuple[str | HardwarePlan | UnifiedPCBModel, dict[str, object]]:
        metadata, pcb_model = _consume_pcb_model(task.metadata)
        if pcb_model is not None:
            if "hardware_plan" in metadata:
                raise PCBAnalysisError(
                    "PCB model context cannot be combined with a hardware plan"
                )
            return pcb_model, metadata
        plan_payload = metadata.pop("hardware_plan", None)
        if plan_payload is None:
            return task.requirement, metadata
        if isinstance(plan_payload, HardwarePlan):
            return plan_payload, metadata
        if isinstance(plan_payload, dict):
            try:
                return HardwarePlan.model_validate(plan_payload), metadata
            except ValidationError as exc:
                raise PCBAnalysisError(
                    "invalid hardware plan for PCB analysis"
                ) from exc
        raise PCBAnalysisError("hardware_plan must be a model or mapping")

    def _analyze(
        self,
        source: str | HardwarePlan,
        metadata: dict[str, object],
    ) -> PCBRequirement:
        try:
            requirement = self._analyzer.analyze(source, metadata=metadata)
            if not isinstance(requirement, PCBRequirement):
                raise TypeError("analyzer returned an invalid requirement")
            return requirement
        except PCBIntelligenceError:
            raise
        except Exception as exc:
            raise PCBAnalysisError("PCB requirement analysis failed") from exc

    def _retrieve_documents(self, query: str) -> list[PCBRuleDocument]:
        try:
            search = getattr(self._retriever, "search", None)
            if callable(search):
                documents = list(search(query))
            else:
                retrieve = getattr(self._retriever, "retrieve", None)
                if not callable(retrieve):
                    raise PCBKnowledgeError(
                        "PCB knowledge retriever must implement search or retrieve"
                    )
                documents = list(retrieve(query))
            if any(not isinstance(document, PCBRuleDocument) for document in documents):
                raise TypeError("retriever returned an invalid PCB document")
            return documents
        except PCBIntelligenceError:
            raise
        except Exception as exc:
            raise PCBKnowledgeError("PCB knowledge retrieval failed") from exc

    def _evaluate_rules(self, requirement: PCBRequirement) -> PCBRuleEvaluation:
        try:
            evaluation = self._rule_engine.evaluate(requirement)
            if not isinstance(evaluation, PCBRuleEvaluation):
                raise TypeError("rule engine returned an invalid evaluation")
            return evaluation
        except PCBIntelligenceError:
            raise
        except Exception as exc:
            raise PCBRuleError("PCB rule evaluation failed") from exc

    def _create_report(
        self,
        requirement: PCBRequirement,
        documents: list[PCBRuleDocument],
        evaluation: PCBRuleEvaluation,
        *,
        pcb_model: UnifiedPCBModel | None,
    ) -> PCBReviewReport:
        try:
            if pcb_model is None:
                report = self._reviewer.review(
                    requirement,
                    documents,
                    evaluation=evaluation,
                )
            else:
                report = self._reviewer.review_structured(
                    requirement,
                    documents,
                    evaluation=evaluation,
                    pcb_model=pcb_model,
                )
            if not isinstance(report, PCBReviewReport):
                raise TypeError("reviewer returned an invalid report")
            return report
        except PCBIntelligenceError:
            raise
        except Exception as exc:
            raise PCBReviewError("PCB review failed") from exc

    def _validate_report(self, report: PCBReviewReport) -> PCBValidationResult:
        try:
            validation = self._validator.validate(report)
            if not isinstance(validation, PCBValidationResult):
                raise TypeError("validator returned an invalid result")
            return validation
        except PCBIntelligenceError:
            raise
        except Exception as exc:
            raise PCBValidationError("PCB review validation failed") from exc

    @staticmethod
    def _safe_error_message(error: PCBIntelligenceError) -> str:
        if isinstance(error, PCBAnalysisError):
            return "PCB requirement analysis failed"
        if isinstance(error, PCBKnowledgeError):
            return "PCB knowledge retrieval failed"
        if isinstance(error, PCBRuleError):
            return "PCB rule evaluation failed"
        if isinstance(error, PCBReviewError):
            return "PCB review failed"
        if isinstance(error, PCBValidationError):
            return "PCB review validation failed"
        return "PCB intelligence pipeline failed"


def _retrieval_query(requirement: PCBRequirement) -> str:
    return " ".join(
        value
        for value in (
            requirement.project_name,
            requirement.platform or "",
            *requirement.components,
            *requirement.interfaces,
            *requirement.constraints,
        )
        if value
    )


def _document_provenance(document: PCBRuleDocument) -> dict[str, object]:
    score = document.metadata.get("retrieval_score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        score = None
    return {
        "id": document.id,
        "title": document.title,
        "category": document.category,
        "retrieval_score": score,
    }
