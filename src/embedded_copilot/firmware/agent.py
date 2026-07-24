from __future__ import annotations

import copy

from pydantic import ValidationError

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.firmware.exceptions import (
    FirmwareAnalysisError,
    FirmwareGenerationError,
    FirmwareIntelligenceError,
    FirmwareKnowledgeError,
    FirmwarePlanningError,
    FirmwareProjectError,
)
from embedded_copilot.firmware.generator import FirmwareGenerator
from embedded_copilot.firmware.intelligence.analyzer import FirmwareRequirementAnalyzer
from embedded_copilot.firmware.knowledge.models import FirmwareDocument
from embedded_copilot.firmware.knowledge.retriever import FirmwareKnowledgeRetriever
from embedded_copilot.firmware.planner.planner import FirmwarePlanner
from embedded_copilot.firmware.project.generator import FirmwareProjectGenerator
from embedded_copilot.firmware.project.validator import FirmwareProjectValidator
from embedded_copilot.firmware.validator import FirmwareValidator
from embedded_copilot.knowledge.injection import extract_centralized_knowledge


class FirmwareAgent(BaseAgent):
    """Foundation-only deterministic firmware request orchestrator."""

    name = "FirmwareAgent"
    description = "Produces validated, unverified mock firmware projects."
    capabilities = ("code_generation", "platform_check")

    def __init__(
        self,
        *,
        analyzer: FirmwareRequirementAnalyzer | None = None,
        retriever: FirmwareKnowledgeRetriever | None = None,
        planner: FirmwarePlanner | None = None,
        generator: FirmwareGenerator | None = None,
        validator: FirmwareValidator | None = None,
        project_generator: FirmwareProjectGenerator | None = None,
        project_validator: FirmwareProjectValidator | None = None,
    ) -> None:
        if project_generator is not None and (
            generator is not None or validator is not None
        ):
            raise ValueError(
                "project_generator cannot be combined with generator or validator"
            )
        self._analyzer = analyzer if analyzer is not None else FirmwareRequirementAnalyzer()
        self._retriever = (
            retriever if retriever is not None else FirmwareKnowledgeRetriever()
        )
        self._planner = planner if planner is not None else FirmwarePlanner()
        self._project_generator = (
            project_generator
            if project_generator is not None
            else FirmwareProjectGenerator(
                code_generator=generator,
                code_validator=validator,
            )
        )
        self._project_validator = (
            project_validator
            if project_validator is not None
            else FirmwareProjectValidator()
        )

    def run(self, task: AgentTask) -> AgentResult:
        try:
            try:
                centralized = extract_centralized_knowledge(
                    task.metadata,
                    field="knowledge_documents",
                    model_type=FirmwareDocument,
                )
            except Exception as exc:
                raise FirmwareKnowledgeError(
                    "firmware knowledge retrieval failed"
                ) from exc
            analysis_metadata = (
                copy.deepcopy(task.metadata)
                if centralized is None
                else centralized[0]
            )
            analysis = self._analyzer.analyze(
                task.requirement,
                metadata=analysis_metadata,
            )
            if centralized is None:
                documents = [
                    document
                    for document in self._retrieve_documents(task.requirement)
                    if (
                        analysis.platform is None
                        or document.platform.casefold() == analysis.platform.casefold()
                    )
                    and (
                        analysis.framework is None
                        or document.framework.casefold()
                        == analysis.framework.casefold()
                    )
                ]
                retrieved_documents = [
                    document.model_dump(mode="json") for document in documents
                ]
            else:
                documents = centralized[1]
                retrieved_documents = centralized[2]
            plan = self._planner.plan(analysis, documents)
            project = self._project_generator.generate(plan)
            validation = self._project_validator.validate(project)
            base_metadata = {
                "firmware_plan": plan.model_dump(mode="json"),
                "retrieved_documents": retrieved_documents,
            }
            if not validation.success:
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.ERROR,
                    output="firmware project validation failed",
                    metadata={
                        **base_metadata,
                        "firmware_project": {
                            "status": "rejected",
                            "platform": plan.platform,
                            "file_count": len(project.files),
                        },
                        "validation": {
                            "success": False,
                            "errors": ["firmware project validation failed"],
                            "warnings": [],
                            "metadata": {"error_count": len(validation.errors)},
                        },
                    },
                )
            intelligence_metadata = {
                **base_metadata,
                "firmware_project": project.model_dump(mode="json"),
                "validation": validation.model_dump(mode="json"),
            }
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                output=project.model_dump_json(),
                metadata=intelligence_metadata,
            )
        except FirmwareIntelligenceError as exc:
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
                output="firmware request validation failed",
                metadata={"error_type": type(exc).__name__},
            )

    def _retrieve_documents(self, query: str) -> list[FirmwareDocument]:
        search = getattr(self._retriever, "search", None)
        if callable(search):
            return list(search(query))
        retrieve = getattr(self._retriever, "retrieve", None)
        if callable(retrieve):
            return list(retrieve(query))
        raise FirmwareKnowledgeError(
            "firmware knowledge retriever must implement search or retrieve"
        )

    @staticmethod
    def _safe_error_message(error: FirmwareIntelligenceError) -> str:
        if isinstance(error, FirmwareAnalysisError):
            return "firmware requirement analysis failed"
        if isinstance(error, FirmwareKnowledgeError):
            return "firmware knowledge retrieval failed"
        if isinstance(error, FirmwarePlanningError):
            return "firmware planning failed: platform is required"
        if isinstance(error, FirmwareProjectError):
            return "firmware project generation failed"
        if isinstance(error, FirmwareGenerationError):
            return "firmware code generation failed"
        return "firmware intelligence pipeline failed"
