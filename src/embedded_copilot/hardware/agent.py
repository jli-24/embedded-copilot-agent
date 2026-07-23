from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.analyzer import HardwareRequirementAnalyzer
from embedded_copilot.hardware.exceptions import (
    HardwareAnalysisError,
    HardwareIntelligenceError,
    HardwareKnowledgeError,
    HardwarePlanningError,
    HardwareValidationError,
)
from embedded_copilot.hardware.knowledge.models import HardwareDocument
from embedded_copilot.hardware.knowledge.retriever import HardwareKnowledgeRetriever
from embedded_copilot.hardware.models import (
    HardwarePlan,
    HardwareRequirement,
    HardwareValidationResult,
)
from embedded_copilot.hardware.planner import HardwarePlanner
from embedded_copilot.hardware.validator import HardwareValidator


class HardwareAgent(BaseAgent):
    """Synchronous deterministic hardware planning agent."""

    name = "HardwareAgent"
    description = "Produces unverified, structured hardware design plans."
    capabilities = ("hardware_analysis", "component_selection")

    def __init__(
        self,
        *,
        analyzer: HardwareRequirementAnalyzer | None = None,
        retriever: HardwareKnowledgeRetriever | None = None,
        planner: HardwarePlanner | None = None,
        validator: HardwareValidator | None = None,
    ) -> None:
        self._analyzer = analyzer if analyzer is not None else HardwareRequirementAnalyzer()
        self._retriever = (
            retriever if retriever is not None else HardwareKnowledgeRetriever()
        )
        self._planner = planner if planner is not None else HardwarePlanner()
        self._validator = validator if validator is not None else HardwareValidator()

    def run(self, task: AgentTask) -> AgentResult:
        try:
            source, metadata = self._resolve_source(task)
            requirement = self._analyze(source, metadata)
            documents = self._retrieve_documents(_retrieval_query(requirement))
            plan = self._create_plan(requirement, documents)
            validation = self._validate_plan(plan)
            if not validation.success:
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.ERROR,
                    output="hardware plan validation failed",
                    metadata={
                        "hardware_plan": {
                            "status": "rejected",
                            "platform": requirement.platform,
                            "mcu": requirement.mcu,
                            "component_count": len(plan.components),
                        },
                        "retrieved_documents": [],
                        "validation": {
                            "success": False,
                            "errors": ["hardware plan validation failed"],
                            "warnings": [],
                            "metadata": {"error_count": len(validation.errors)},
                        },
                    },
                )

            plan_payload = plan.model_dump(mode="json")
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                output=plan.model_dump_json(),
                metadata={
                    "hardware_plan": plan_payload,
                    "retrieved_documents": [
                        document.model_dump(mode="json") for document in documents
                    ],
                    "validation": validation.model_dump(mode="json"),
                },
            )
        except HardwareIntelligenceError as exc:
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
                output="hardware request validation failed",
                metadata={"error_type": type(exc).__name__},
            )

    @staticmethod
    def _resolve_source(
        task: AgentTask,
    ) -> tuple[str | FirmwareProject, dict[str, object]]:
        metadata = dict(task.metadata)
        project_payload = metadata.pop("firmware_project", None)
        if project_payload is None:
            return task.requirement, metadata
        if isinstance(project_payload, FirmwareProject):
            return project_payload, metadata
        if isinstance(project_payload, dict):
            try:
                return FirmwareProject.model_validate(project_payload), metadata
            except ValidationError as exc:
                raise HardwareAnalysisError(
                    "invalid firmware project for hardware analysis"
                ) from exc
        raise HardwareAnalysisError("firmware_project must be a model or mapping")

    def _retrieve_documents(self, query: str) -> list[HardwareDocument]:
        try:
            search = getattr(self._retriever, "search", None)
            if callable(search):
                return list(search(query))
            retrieve = getattr(self._retriever, "retrieve", None)
            if callable(retrieve):
                return list(retrieve(query))
            raise HardwareKnowledgeError(
                "hardware knowledge retriever must implement search or retrieve"
            )
        except HardwareIntelligenceError:
            raise
        except Exception as exc:
            raise HardwareKnowledgeError(
                "hardware knowledge retrieval failed"
            ) from exc

    def _analyze(
        self,
        source: str | FirmwareProject,
        metadata: dict[str, object],
    ) -> HardwareRequirement:
        try:
            return self._analyzer.analyze(source, metadata=metadata)
        except HardwareIntelligenceError:
            raise
        except Exception as exc:
            raise HardwareAnalysisError(
                "hardware requirement analysis failed"
            ) from exc

    def _create_plan(
        self,
        requirement: HardwareRequirement,
        documents: list[HardwareDocument],
    ) -> HardwarePlan:
        try:
            return self._planner.plan(requirement, documents)
        except HardwareIntelligenceError:
            raise
        except Exception as exc:
            raise HardwarePlanningError("hardware planning failed") from exc

    def _validate_plan(self, plan: HardwarePlan) -> HardwareValidationResult:
        try:
            return self._validator.validate(plan)
        except HardwareIntelligenceError:
            raise
        except Exception as exc:
            raise HardwareValidationError(
                "hardware plan validation failed"
            ) from exc

    @staticmethod
    def _safe_error_message(error: HardwareIntelligenceError) -> str:
        if isinstance(error, HardwareAnalysisError):
            return "hardware requirement analysis failed"
        if isinstance(error, HardwareKnowledgeError):
            return "hardware knowledge retrieval failed"
        if isinstance(error, HardwarePlanningError):
            return "hardware planning failed"
        if isinstance(error, HardwareValidationError):
            return "hardware plan validation failed"
        return "hardware intelligence pipeline failed"


def _retrieval_query(requirement: object) -> str:
    return " ".join(
        value
        for value in (
            getattr(requirement, "requirement", ""),
            getattr(requirement, "platform", "") or "",
            getattr(requirement, "mcu", "") or "",
            *getattr(requirement, "peripherals", []),
            *getattr(requirement, "interfaces", []),
        )
        if value
    )
