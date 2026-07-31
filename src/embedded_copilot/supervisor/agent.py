from __future__ import annotations

import copy
from collections.abc import Iterable
from uuid import uuid4

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.debug.agent import DebugAgent
from embedded_copilot.engineering_memory.context import (
    MemoryContext,
    MemoryRetrievalRequest,
)
from embedded_copilot.engineering_memory.context_builder import (
    RankedMemoryContext,
    build_memory_context,
)
from embedded_copilot.engineering_memory.ranking import RankedMemoryItem
from embedded_copilot.engineering_memory.retrieval import EngineeringMemoryRetriever
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
from embedded_copilot.input.adapters.supervisor import _CONTEXT_KEY
from embedded_copilot.knowledge.gateway import KnowledgeGateway
from embedded_copilot.knowledge.models import KnowledgeQuery, KnowledgeResult
from embedded_copilot.knowledge.source import project_result
from embedded_copilot.pcb.agent import PCBAgent
from embedded_copilot.supervisor.aggregator import SupervisorResultAggregator
from embedded_copilot.supervisor.analyzer import SupervisorRequirementAnalyzer
from embedded_copilot.supervisor.context import (
    EngineeringPlanningContext,
    ExecutionContext,
    KnowledgeContext,
    PlanningKnowledgeContext,
    PlanningKnowledgeEvidence,
    SupervisorFallbackTraceEvent,
    SupervisorMemoryTraceEvent,
    SupervisorTraceEvent,
    build_engineering_planning_context,
    project_safe_supervisor_metadata,
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
        memory_retriever: EngineeringMemoryRetriever | None = None,
        memory_binding: MemoryRetrievalRequest | None = None,
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
        self._memory_retriever = memory_retriever
        if memory_binding is None:
            self._memory_binding = None
        else:
            if not isinstance(memory_binding, MemoryRetrievalRequest):
                raise TypeError("memory_binding must be a MemoryRetrievalRequest")
            self._memory_binding = MemoryRetrievalRequest.model_validate(
                copy.deepcopy(memory_binding)
            )

    def run(self, task: AgentTask) -> AgentResult:
        plan: SupervisorPlan | None = None
        results: list[AgentResult] = []
        integration_results: tuple[AgentExecutionResult, ...] = ()
        integration_trace: list[IntegrationTraceEvent] = []
        execution_context: ExecutionContext | None = None
        planning_context: EngineeringPlanningContext | None = None
        memory_trace: list[SupervisorMemoryTraceEvent] = []
        fallback_trace: list[SupervisorFallbackTraceEvent] = []
        if not isinstance(task, AgentTask):
            return self._safe_failure(
                SupervisorAnalysisError,
                plan,
                results,
                memory_trace=memory_trace,
                fallback_trace=fallback_trace,
            )
        try:
            safe_task = self._safe_task(task)
            analyzed = self._analyzer.analyze(
                safe_task.requirement,
                metadata=safe_task.model_copy(deep=True).metadata,
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
            explicit_agents = "required_agents" in safe_task.metadata
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
            return self._safe_failure(
                SupervisorAnalysisError,
                plan,
                results,
                memory_trace=memory_trace,
                fallback_trace=fallback_trace,
            )

        ranked_memory_context: RankedMemoryContext | None = None
        if self._memory_binding is not None:
            memory_trace.append(
                SupervisorMemoryTraceEvent(
                    event="retrieval_attempted",
                    memory_count=0,
                )
            )
            try:
                retrieve = getattr(self._memory_retriever, "retrieve", None)
                if not callable(retrieve):
                    raise TypeError("memory retriever is unavailable")
                request = MemoryRetrievalRequest.model_validate(
                    copy.deepcopy(self._memory_binding)
                )
                raw_memory_context = retrieve(request)
                if not isinstance(raw_memory_context, MemoryContext):
                    raise TypeError("memory retriever returned an invalid context")
                checked_memory_context = MemoryContext.model_validate(
                    copy.deepcopy(raw_memory_context)
                )
                ranked_memory_context = self._planning_memory_context(
                    checked_memory_context
                )
                memory_trace.append(
                    SupervisorMemoryTraceEvent(
                        event="retrieval_succeeded",
                        memory_count=len(checked_memory_context.records),
                    )
                )
            except Exception:
                ranked_memory_context = None
                memory_trace.append(
                    SupervisorMemoryTraceEvent(
                        event="retrieval_failed",
                        memory_count=0,
                    )
                )
                fallback_trace.extend(
                    (
                        SupervisorFallbackTraceEvent(
                            event="memory_failed",
                            stage="MemoryUnavailable",
                            memory_count=0,
                        ),
                        SupervisorFallbackTraceEvent(
                            event="fallback_used",
                            stage="MemoryUnavailable",
                            memory_count=0,
                        ),
                    )
                )

        if self._knowledge_gateway is not None:
            try:
                query, gateway_query, before, trace, domains = (
                    self._prepare_knowledge_query(analyzed)
                )
                raw_results = self._knowledge_gateway.search(gateway_query)
                after = copy.deepcopy(gateway_query.model_dump(mode="json"))
                if after != before:
                    raise ValueError("knowledge gateway modified query")
                candidate_execution_context = self._build_execution_context(
                    safe_task,
                    query,
                    raw_results,
                    trace,
                    domains,
                )
                candidate_analyzed = self._planning_task(
                    analyzed,
                    candidate_execution_context,
                )
                execution_context = candidate_execution_context
                analyzed = candidate_analyzed
            except Exception:
                if self._memory_binding is None:
                    return self._safe_failure(
                        SupervisorKnowledgeError,
                        plan,
                        results,
                        memory_trace=memory_trace,
                        fallback_trace=fallback_trace,
                    )
                execution_context = None
                memory_count = (
                    len(ranked_memory_context.records)
                    if ranked_memory_context is not None
                    else 0
                )
                fallback_trace.extend(
                    (
                        SupervisorFallbackTraceEvent(
                            event="knowledge_failed",
                            stage="KnowledgeUnavailable",
                            memory_count=memory_count,
                        ),
                        SupervisorFallbackTraceEvent(
                            event="fallback_used",
                            stage="KnowledgeUnavailable",
                            memory_count=memory_count,
                        ),
                    )
                )

        if self._memory_binding is not None:
            try:
                planning_context = build_engineering_planning_context(
                    knowledge_context=self._planning_knowledge_context(
                        execution_context
                    ),
                    memory_context=ranked_memory_context,
                )
            except Exception:
                planning_context = None
                fallback_trace.extend(
                    (
                        SupervisorFallbackTraceEvent(
                            event="fusion_failed",
                            stage="FusionUnavailable",
                            memory_count=0,
                        ),
                        SupervisorFallbackTraceEvent(
                            event="fallback_used",
                            stage="FusionUnavailable",
                            memory_count=0,
                        ),
                    )
                )

        try:
            plan_with_context = getattr(self._planner, "plan_with_context", None)
            if planning_context is not None and callable(plan_with_context):
                try:
                    plan = self._checked_plan(
                        plan_with_context(
                            analyzed.model_copy(deep=True),
                            planning_context.model_copy(deep=True),
                        )
                    )
                except Exception:
                    fallback_trace.append(
                        SupervisorFallbackTraceEvent(
                            event="fallback_used",
                            stage="FusionUnavailable",
                            memory_count=0,
                        )
                    )
                    plan = self._checked_plan(
                        self._planner.plan(analyzed.model_copy(deep=True))
                    )
            else:
                if planning_context is not None:
                    fallback_trace.append(
                        SupervisorFallbackTraceEvent(
                            event="fallback_used",
                            stage="FusionUnavailable",
                            memory_count=0,
                        )
                    )
                plan = self._checked_plan(
                    self._planner.plan(analyzed.model_copy(deep=True))
                )
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
            return self._safe_failure(
                SupervisorPlanningError,
                plan,
                results,
                memory_trace=memory_trace,
                fallback_trace=fallback_trace,
            )

        try:
            dispatched, integration_results = (
                    self._integration_executor.execute_with_results(
                    safe_task.model_copy(deep=True),
                    plan.model_copy(deep=True),
                    execution_context=execution_context,
                )
            )
            results = list(dispatched)
        except Exception:
            return self._safe_failure(
                SupervisorDispatchError,
                plan,
                results,
                memory_trace=memory_trace,
                fallback_trace=fallback_trace,
            )

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
                request=safe_task.requirement,
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
            return self._safe_failure(
                SupervisorAggregationError,
                plan,
                results,
                memory_trace=memory_trace,
                fallback_trace=fallback_trace,
            )

        metadata: dict[str, object] = {
            "supervisor_plan": plan.model_dump(mode="json"),
            "agent_results": [
                result.model_dump(mode="json") for result in results
            ],
            "execution_summary": report.model_dump(mode="json"),
            "engineering_report": engineering_report.model_dump(mode="json"),
        }
        if memory_trace:
            metadata["memory_trace"] = [
                event.model_dump(mode="json") for event in memory_trace
            ]
        if fallback_trace:
            metadata["fallback_trace"] = [
                event.model_dump(mode="json") for event in fallback_trace
            ]
        return AgentResult(
            agent_name=self.name,
            status=(AgentStatus.ERROR if report.failed else AgentStatus.SUCCESS),
            output=report.model_dump_json(),
            metadata=metadata,
        )

    @staticmethod
    def _safe_task(value: AgentTask) -> AgentTask:
        isolated = value.model_copy(deep=True)
        metadata = dict(isolated.metadata)
        missing_context = object()
        input_context = metadata.pop(_CONTEXT_KEY, missing_context)
        safe_metadata = project_safe_supervisor_metadata(metadata)
        if input_context is not missing_context:
            safe_metadata[_CONTEXT_KEY] = input_context
        return isolated.model_copy(update={"metadata": safe_metadata}, deep=True)

    @staticmethod
    def _checked_plan(value: object) -> SupervisorPlan:
        if not isinstance(value, SupervisorPlan):
            raise TypeError("planner returned an invalid plan")
        return SupervisorPlan.model_validate(value.model_dump(mode="json"))

    @staticmethod
    def _planning_memory_context(value: MemoryContext) -> RankedMemoryContext:
        items = tuple(
            RankedMemoryItem(
                record_id=item.record_id,
                memory_type=item.memory_type,
                logical_key=item.logical_key,
                ranking=item.ranking,
            )
            for item in value.evidence
        )
        return build_memory_context(
            items,
            evidence=value.evidence,
        )

    @staticmethod
    def _planning_knowledge_context(
        execution_context: ExecutionContext | None,
    ) -> PlanningKnowledgeContext | None:
        if execution_context is None:
            return None
        sources: list[PlanningKnowledgeEvidence] = []
        for document in execution_context.knowledge_context.retrieved_documents:
            projected = project_result(document)
            sources.append(
                PlanningKnowledgeEvidence(
                    source_id=projected.source_id,
                    source_type=projected.source_type,
                    reference=projected.source_id,
                    trust_level=0.5,
                )
            )
        return PlanningKnowledgeContext(sources=tuple(sources))

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
        *,
        memory_trace: list[SupervisorMemoryTraceEvent] | None = None,
        fallback_trace: list[SupervisorFallbackTraceEvent] | None = None,
    ) -> AgentResult:
        messages: dict[type[SupervisorIntelligenceError], str] = {
            SupervisorAnalysisError: "supervisor requirement analysis failed",
            SupervisorPlanningError: "supervisor planning failed",
            SupervisorKnowledgeError: "supervisor knowledge integration failed",
            SupervisorDispatchError: "supervisor dispatch failed",
            SupervisorAggregationError: "supervisor aggregation failed",
        }
        metadata: dict[str, object] = {
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
        }
        if memory_trace:
            metadata["memory_trace"] = [
                event.model_dump(mode="json") for event in memory_trace
            ]
        if fallback_trace:
            metadata["fallback_trace"] = [
                event.model_dump(mode="json") for event in fallback_trace
            ]
        return AgentResult(
            agent_name=cls.name,
            status=AgentStatus.ERROR,
            output=messages[error_type],
            metadata=metadata,
        )
