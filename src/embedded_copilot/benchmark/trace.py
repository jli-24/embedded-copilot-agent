from __future__ import annotations

import copy
import time
from collections.abc import Callable, Mapping

from embedded_copilot.benchmark.models import (
    BenchmarkTrace,
    ExecutionMetrics,
    TraceEvent,
)


def _status(value: object) -> str:
    candidate = getattr(value, "value", value)
    return "success" if candidate == "success" else "error"


class TraceCollector:
    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock if clock is not None else time.perf_counter

    def start(self) -> float:
        return self._clock()

    def collect(
        self,
        *,
        case_id: str,
        target_name: str,
        result: object,
        started_at: float,
        execution_succeeded: bool,
    ) -> BenchmarkTrace:
        elapsed_ms = round(max(0.0, (self._clock() - started_at) * 1000), 9)
        if target_name == "SupervisorAgent" and execution_succeeded:
            events = self._supervisor_events(result)
            agent_calls = sum(event.event_type == "agent_call" for event in events)
            knowledge_calls = 0
        elif target_name == "KnowledgeGateway":
            events = [
                TraceEvent(
                    sequence=1,
                    event_type="knowledge_call",
                    target=target_name,
                    status="success" if execution_succeeded else "error",
                )
            ]
            agent_calls = 0
            knowledge_calls = 1
        else:
            status = (
                _status(getattr(result, "status", None))
                if execution_succeeded
                else "error"
            )
            events = [
                TraceEvent(
                    sequence=1,
                    event_type="agent_call",
                    target=target_name,
                    status=status,
                )
            ]
            agent_calls = 1
            knowledge_calls = 0
        return BenchmarkTrace(
            case_id=case_id,
            events=events,
            execution_metrics=ExecutionMetrics(
                execution_time_ms=elapsed_ms,
                agent_calls=agent_calls,
                knowledge_calls=knowledge_calls,
            ),
        )

    @staticmethod
    def _supervisor_events(result: object) -> list[TraceEvent]:
        metadata = copy.deepcopy(getattr(result, "metadata", {}))
        if not isinstance(metadata, Mapping):
            return []
        plan = metadata.get("supervisor_plan")
        raw_results = metadata.get("agent_results")
        if not isinstance(plan, Mapping) or not isinstance(raw_results, list):
            return []
        tasks = plan.get("tasks")
        if not isinstance(tasks, list):
            return []
        statuses: dict[str, str] = {}
        for raw_result in raw_results:
            if not isinstance(raw_result, Mapping):
                continue
            name = raw_result.get("agent_name")
            if isinstance(name, str) and name.strip():
                statuses[name.strip().casefold()] = _status(raw_result.get("status"))
        names: list[str] = []
        for task in tasks:
            if not isinstance(task, Mapping):
                continue
            name = task.get("agent_name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
        events: list[TraceEvent] = []
        for index, name in enumerate(names):
            current_status = statuses.get(name.casefold(), "error")
            if index:
                previous = names[index - 1]
                previous_status = statuses.get(previous.casefold(), "error")
                events.append(
                    TraceEvent(
                        sequence=len(events) + 1,
                        event_type="handoff",
                        target=name,
                        status=(
                            "success"
                            if current_status == previous_status == "success"
                            else "error"
                        ),
                        handoff_from=previous,
                        handoff_to=name,
                    )
                )
            events.append(
                TraceEvent(
                    sequence=len(events) + 1,
                    event_type="agent_call",
                    target=name,
                    status=current_status,
                )
            )
        return events
