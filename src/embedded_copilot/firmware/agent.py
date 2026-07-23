from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.firmware.exceptions import (
    FirmwareAnalysisError,
    FirmwareGenerationError,
    FirmwareIntelligenceError,
    FirmwareKnowledgeError,
    FirmwarePlanningError,
)
from embedded_copilot.firmware.generator import FirmwareGenerator
from embedded_copilot.firmware.intelligence.analyzer import FirmwareRequirementAnalyzer
from embedded_copilot.firmware.knowledge.models import FirmwareDocument
from embedded_copilot.firmware.knowledge.retriever import FirmwareKnowledgeRetriever
from embedded_copilot.firmware.planner.planner import FirmwarePlanner
from embedded_copilot.firmware.validator import FirmwareValidator


class FirmwareAgent(BaseAgent):
    """Foundation-only deterministic firmware request orchestrator."""

    name = "FirmwareAgent"
    description = "Validates firmware requests and produces unverified mock code."
    capabilities = ("code_generation", "platform_check")

    def __init__(
        self,
        *,
        analyzer: FirmwareRequirementAnalyzer | None = None,
        retriever: FirmwareKnowledgeRetriever | None = None,
        planner: FirmwarePlanner | None = None,
        generator: FirmwareGenerator | None = None,
        validator: FirmwareValidator | None = None,
    ) -> None:
        self._analyzer = analyzer if analyzer is not None else FirmwareRequirementAnalyzer()
        self._retriever = (
            retriever if retriever is not None else FirmwareKnowledgeRetriever()
        )
        self._planner = planner if planner is not None else FirmwarePlanner()
        self._generator = generator if generator is not None else FirmwareGenerator()
        self._validator = validator if validator is not None else FirmwareValidator()

    def run(self, task: AgentTask) -> AgentResult:
        try:
            analysis = self._analyzer.analyze(
                task.requirement,
                metadata=task.metadata,
            )
            documents = [
                document
                for document in self._retrieve_documents(task.requirement)
                if (
                    analysis.platform is None
                    or document.platform.casefold() == analysis.platform.casefold()
                )
                and (
                    analysis.framework is None
                    or document.framework.casefold() == analysis.framework.casefold()
                )
            ]
            plan = self._planner.plan(analysis, documents)
            request = plan.to_firmware_request(
                requirement=analysis.requirement,
                metadata=analysis.metadata,
            )
            generated = self._generator.generate(request)
            validation = self._validator.validate(generated)
            validation_payload = validation.model_dump(mode="json")
            intelligence_metadata = {
                "firmware_plan": plan.model_dump(mode="json"),
                "retrieved_documents": [
                    document.model_dump(mode="json") for document in documents
                ],
                "validation": validation_payload,
            }
            if not validation.success:
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.ERROR,
                    output="; ".join(validation.errors),
                    metadata=intelligence_metadata,
                )
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                output=generated.model_dump_json(),
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
        if isinstance(error, FirmwareGenerationError):
            return "firmware code generation failed"
        return "firmware intelligence pipeline failed"
