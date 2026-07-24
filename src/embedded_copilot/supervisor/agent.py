from __future__ import annotations

import copy
from collections.abc import Iterable
from uuid import uuid4

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.debug.agent import DebugAgent
from embedded_copilot.firmware.agent import FirmwareAgent
from embedded_copilot.hardware.agent import HardwareAgent
from embedded_copilot.integration.aggregator import ResultAggregator
from embedded_copilot.integration.context import (
    AgentExecutionResult,
    EngineeringContext,
    IntegrationTraceEvent,
)
from embedded_copilot.integration.executor import AgentExecutor
from embedded_copilot.integration.planner import IntegrationPlanner
from embedded_copilot.knowledge.gateway import KnowledgeGateway
from embedded_copilot.knowledge.models import KnowledgeQuery, KnowledgeResult
from embedded_copilot.pcb.agent import PCBAgent
from embedded_copilot.supervisor.aggregator import SupervisorResultAggregator
from embedded_copilot.supervisor.analyzer import SupervisorRequirementAnalyzer
from embedded_copilot.supervisor.context import (
    ExecutionContext,
    KnowledgeContext,
    SupervisorTraceEvent,
)
from embedded_copilot.supervisor.dispatcher import AgentDispatcher
from embedded_copilot.supervisor.exceptions import (
    SupervisorAggregationError,
    SupervisorAnalysisError,
    SupervisorDispatchError,
    SupervisorIntelligenceError,
    SupervisorKnowledgeError,
    SupervisorPlanningError,
)
from embedded_copilot.supervisor.knowledge_adapters import knowledge_categories
from embedded_copilot.supervisor.knowledge_query import KnowledgeQueryBuilder
from embedded_copilot.supervisor.models import (
    SupervisorPlan,
    SupervisorResult,
    SupervisorTask,
)
from embedded_copilot.supervisor.planner import SupervisorPlanner


class SupervisorAgent(BaseAgent):
    """Synchronous deterministic Foundation Supervisor."""

    name = "SupervisorAgent"
    description = "Plans and orchestrates deterministic Foundation Agents."
    capabilities = (
        "task_planning",
        "agent_orchestration",
        "result_aggregation",
    )

    def __init__(
        self,
        *,
        analyzer: SupervisorRequirementAnalyzer | None = None,
        planner: SupervisorPlanner | None = None,
        dispatcher: AgentDispatcher | None = None,
        aggregator: SupervisorResultAggregator | None = None,
        agents: Iterable[BaseAgent] | None = None,
        knowledge_gateway: KnowledgeGateway | None = None,
        knowledge_query_builder: KnowledgeQueryBuilder | None = None,
    ) -> None:
        if dispatcher is not None and agents is not None:
            raise ValueError("dispatcher and agents cannot be provided together")
        self._analyzer = (
            analyzer if analyzer is not None else SupervisorRequirementAnalyzer()
        )
        self._planner = planner if planner is not None else SupervisorPlanner()
        if dispatcher is not None:
            self._dispatcher = dispatcher
        else:
            active_agents = (
                agents
                if agents is not None
                else (FirmwareAgent(), HardwareAgent(), PCBAgent(), DebugAgent())
            )
            self._dispatcher = AgentDispatcher(active_agents)
        self._aggregator = (
            aggregator if aggregator is not None else SupervisorResultAggregator()
        )
        self._integration_planner = IntegrationPlanner()
        self._integration_executor = AgentExecutor(self._dispatcher)
        self._integration_aggregator = ResultAggregator()
        self._knowledge_gateway = knowledge_gateway
        self._knowledge_query_builder = (
            knowledge_query_builder
            if knowledge_query_builder is not None
            else KnowledgeQueryBuilder()
        )

    def run(self, task: AgentTask) -> AgentResult:
        plan: SupervisorPlan | None = None
        results: list[AgentResult] = []
        integration_results: tuple[AgentExecutionResult, ...] = ()
        integration_trace: list[IntegrationTraceEvent] = []
        execution_context: ExecutionContext | None = None
        if not isinstance(task, AgentTask):
            return self._safe_failure(SupervisorAnalysisError, plan, results)
        try:
            analyzed = self._analyzer.analyze(
                task.requirement,
                metadata=task.model_copy(deep=True).metadata,
            )
            if not isinstance(analyzed, SupervisorTask):
                raise TypeError("analyzer returned an invalid task")
            analyzed = SupervisorTask.model_validate(
                analyzed.model_dump(mode="json")
            )
            context = EngineeringContext(
                request=analyzed.request,
                input_context=analyzed.input_context,
            )
            explicit_agents = "required_agents" in task.metadata
            selected_agents = self._integration_planner.select_agents(
                context,
                required_agents=(
                    analyzed.required_agents if explicit_agents else None
                ),
                seed_agents=(None if explicit_agents else analyzed.required_agents),
            )
            analyzed_payload = analyzed.model_dump(mode="python")
            analyzed_payload["required_agents"] = list(selected_agents)
            analyzed = SupervisorTask.model_validate(analyzed_payload)
            integration_trace.append(
                IntegrationTraceEvent(
                    sequence=1,
                    stage="input_analyzed",
                    status="success",
                    source_agent="SupervisorAgent",
                    source_id="supervisor:input-analysis",
                )
            )
        except Exception:
            return self._safe_failure(SupervisorAnalysisError, plan, results)

        if self._knowledge_gateway is not None:
            try:
                query, gateway_query, before, trace, domains = (
                    self._prepare_knowledge_query(analyzed)
                )
                raw_results = self._knowledge_gateway.search(gateway_query)
                after = copy.deepcopy(gateway_query.model_dump(mode="json"))
                if after != before:
                    raise ValueError("knowledge gateway modified query")
                execution_context = self._build_execution_context(
                    task,
                    query,
                    raw_results,
                    trace,
                    domains,
                )
                analyzed = self._planning_task(analyzed, execution_context)
            except Exception:
                return self._safe_failure(SupervisorKnowledgeError, plan, results)

        try:
            planned = self._planner.plan(analyzed.model_copy(deep=True))
            if not isinstance(planned, SupervisorPlan):
                raise TypeError("planner returned an invalid plan")
            plan = SupervisorPlan.model_validate(planned.model_dump(mode="json"))
            if execution_context is not None:
                integration_trace.append(
                    IntegrationTraceEvent(
                        sequence=len(integration_trace) + 1,
                        stage="knowledge_consumed",
                        status="success",
                        source_agent="SupervisorAgent",
                        source_id="supervisor:knowledge-context",
                    )
                )
            for invocation in plan.tasks:
                integration_trace.append(
                    IntegrationTraceEvent(
                        sequence=len(integration_trace) + 1,
                        stage="agent_planned",
                        status="success",
                        source_agent="SupervisorAgent",
                        source_id=f"supervisor:plan:{invocation.agent_name}",
                    )
                )
        except Exception:
            return self._safe_failure(SupervisorPlanningError, plan, results)

        try:
            dispatched, integration_results = (
                self._integration_executor.execute_with_results(
                    task.model_copy(deep=True),
                    plan.model_copy(deep=True),
                    execution_context=execution_context,
                )
            )
            results = list(dispatched)
        except Exception:
            return self._safe_failure(SupervisorDispatchError, plan, results)

        try:
            aggregated = self._aggregator.aggregate(
                plan.model_copy(deep=True),
                [result.model_copy(deep=True) for result in results],
            )
            if not isinstance(aggregated, SupervisorResult):
                raise TypeError("aggregator returned an invalid result")
            report = SupervisorResult.model_validate(
                aggregated.model_dump(mode="json")
            )
            if execution_context is not None:
                report = self._with_trace(report, execution_context, results)
            engineering_context = EngineeringContext(
                request=task.requirement,
                input_context=analyzed.input_context,
                knowledge_context=(
                    execution_context.knowledge_context
                    if execution_context is not None
                    else None
                ),
                agent_results=integration_results,
                trace=tuple(integration_trace),
            )
            engineering_report = self._integration_aggregator.aggregate(
                engineering_context.agent_results,
                trace=engineering_context.trace,
            )
        except Exception:
            return self._safe_failure(SupervisorAggregationError, plan, results)

        return AgentResult(
            agent_name=self.name,
            status=(AgentStatus.ERROR if report.failed else AgentStatus.SUCCESS),
            output=report.model_dump_json(),
            metadata={
                "supervisor_plan": plan.model_dump(mode="json"),
                "agent_results": [
                    result.model_dump(mode="json") for result in results
                ],
                "execution_summary": report.model_dump(mode="json"),
                "engineering_report": engineering_report.model_dump(mode="json"),
            },
        )

    def _prepare_knowledge_query(
        self,
        analyzed: SupervisorTask,
    ) -> tuple[
        KnowledgeQuery,
        KnowledgeQuery,
        dict[str, object],
        list[SupervisorTraceEvent],
        tuple[str, ...],
    ]:
        agent_domains = {
            "FirmwareAgent": "firmware",
            "HardwareAgent": "hardware",
            "PCBAgent": "pcb",
            "DebugAgent": "debug",
        }
        domains = tuple(
            agent_domains[name]
            for name in analyzed.required_agents
            if name in agent_domains
        )
        trace = [
            SupervisorTraceEvent(
                stage="task_parsed",
                status="success",
                target=self.name,
                domains=domains,
                count=len(analyzed.required_agents),
            )
        ]
        raw_query = self._knowledge_query_builder.build(analyzed.model_copy(deep=True))
        if not isinstance(raw_query, KnowledgeQuery):
            raise TypeError("knowledge query builder returned an invalid query")
        query = KnowledgeQuery.model_validate(
            copy.deepcopy(raw_query.model_dump(mode="python"))
        )
        keywords = query.metadata.get("keywords", [])
        trace.append(
            SupervisorTraceEvent(
                stage="knowledge_query_built",
                status="success",
                target="KnowledgeQueryBuilder",
                domains=domains,
                count=len(keywords) if isinstance(keywords, list) else 0,
            )
        )
        gateway_query = KnowledgeQuery.model_validate(
            copy.deepcopy(query.model_dump(mode="python"))
        )
        before = copy.deepcopy(gateway_query.model_dump(mode="json"))
        return query, gateway_query, before, trace, domains

    @staticmethod
    def _build_execution_context(
        task: AgentTask,
        query: KnowledgeQuery,
        raw_results: object,
        trace: list[SupervisorTraceEvent],
        domains: tuple[str, ...],
    ) -> ExecutionContext:
        if not isinstance(raw_results, list):
            raise TypeError("knowledge gateway returned an invalid container")
        documents: list[KnowledgeResult] = []
        for raw_result in raw_results:
            if not isinstance(raw_result, KnowledgeResult):
                raise TypeError("knowledge gateway returned an invalid result")
            documents.append(
                KnowledgeResult.model_validate(
                    copy.deepcopy(raw_result.model_dump(mode="python"))
                )
            )
        trace.append(
            SupervisorTraceEvent(
                stage="gateway_retrieved",
                status="success",
                target="KnowledgeGateway",
                domains=domains,
                count=len(documents),
            )
        )
        knowledge_context = KnowledgeContext(
            query=query,
            retrieved_documents=tuple(documents),
            summary=f"Retrieved {len(documents)} knowledge result(s).",
        )
        trace.append(
            SupervisorTraceEvent(
                stage="context_built",
                status="success",
                target="KnowledgeContext",
                domains=domains,
                count=len(documents),
            )
        )
        return ExecutionContext(
            task=AgentTask.model_validate(
                copy.deepcopy(task.model_dump(mode="python"))
            ),
            knowledge_context=knowledge_context,
            trace=tuple(trace),
            execution_id=uuid4(),
        )

    @staticmethod
    def _planning_task(
        analyzed: SupervisorTask,
        execution_context: ExecutionContext,
    ) -> SupervisorTask:
        raw_domains = execution_context.knowledge_context.query.metadata.get(
            "domains",
            [],
        )
        domains = (
            [item for item in raw_domains if isinstance(item, str) and item]
            if isinstance(raw_domains, list)
            else []
        )
        categories = knowledge_categories(
            execution_context.knowledge_context.retrieved_documents
        )
        metadata = copy.deepcopy(analyzed.metadata)
        metadata["_supervisor_knowledge"] = {
            "domains": domains,
            "result_count": len(
                execution_context.knowledge_context.retrieved_documents
            ),
            "categories": categories,
            "has_results": bool(
                execution_context.knowledge_context.retrieved_documents
            ),
        }
        payload = copy.deepcopy(analyzed.model_dump(mode="python"))
        payload["metadata"] = metadata
        return SupervisorTask.model_validate(payload)

    @staticmethod
    def _with_trace(
        report: SupervisorResult,
        execution_context: ExecutionContext,
        results: list[AgentResult],
    ) -> SupervisorResult:
        domains_by_agent = {
            "FirmwareAgent": ("firmware",),
            "HardwareAgent": ("hardware",),
            "PCBAgent": ("pcb",),
            "DebugAgent": ("debug",),
        }
        events = list(execution_context.trace)
        for result in results:
            events.append(
                SupervisorTraceEvent(
                    stage="agent_routed",
                    status=(
                        "success"
                        if result.status is AgentStatus.SUCCESS
                        else "error"
                    ),
                    target=result.agent_name,
                    domains=domains_by_agent.get(result.agent_name, ()),
                    count=1,
                )
            )
        events.append(
            SupervisorTraceEvent(
                stage="finished",
                status="error" if report.failed else "success",
                target="SupervisorAgent",
                domains=tuple(
                    domain
                    for result in results
                    for domain in domains_by_agent.get(result.agent_name, ())
                ),
                count=len(results),
            )
        )
        metadata = copy.deepcopy(report.metadata)
        metadata["supervisor_trace"] = [
            event.model_dump(mode="json") for event in events
        ]
        payload = report.model_dump(mode="python")
        payload["metadata"] = metadata
        return SupervisorResult.model_validate(payload)

    @classmethod
    def _safe_failure(
        cls,
        error_type: type[SupervisorIntelligenceError],
        plan: SupervisorPlan | None,
        results: list[AgentResult],
    ) -> AgentResult:
        messages: dict[type[SupervisorIntelligenceError], str] = {
            SupervisorAnalysisError: "supervisor requirement analysis failed",
            SupervisorPlanningError: "supervisor planning failed",
            SupervisorKnowledgeError: "supervisor knowledge integration failed",
            SupervisorDispatchError: "supervisor dispatch failed",
            SupervisorAggregationError: "supervisor aggregation failed",
        }
        return AgentResult(
            agent_name=cls.name,
            status=AgentStatus.ERROR,
            output=messages[error_type],
            metadata={
                "supervisor_plan": (
                    plan.model_dump(mode="json") if plan is not None else None
                ),
                "agent_results": [
                    result.model_dump(mode="json") for result in results
                ],
                "execution_summary": {
                    "status": "error",
                    "error_type": error_type.__name__,
                },
            },
        )
