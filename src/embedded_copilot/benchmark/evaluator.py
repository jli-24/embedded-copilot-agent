from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field, field_validator, model_validator

from embedded_copilot.benchmark.exceptions import BenchmarkEvaluationError
from embedded_copilot.benchmark.metrics import (
    AccuracyMetric,
    CapabilityCoverageMetric,
    CoverageMetric,
    ScoreAggregator,
)
from embedded_copilot.benchmark.models import (
    BenchmarkCase,
    BenchmarkResult,
    BenchmarkTrace,
)
from embedded_copilot.schemas.result import ContractModel


def _normalize_list(value: object) -> object:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        return value
    result: list[object] = []
    seen: set[str] = set()
    for item in value:
        candidate = item.strip() if isinstance(item, str) else item
        if isinstance(candidate, str):
            if not candidate:
                raise ValueError("expected list values must not be empty")
            key = candidate.casefold()
            if key in seen:
                continue
            seen.add(key)
        result.append(candidate)
    return result


class _AgentChainExpected(ContractModel):
    agents: list[str]
    capabilities: list[str]

    @field_validator("agents", "capabilities", mode="before")
    @classmethod
    def normalize_lists(cls, value: object) -> object:
        return _normalize_list(value)

    @model_validator(mode="after")
    def require_values(self) -> "_AgentChainExpected":
        if not self.agents or not self.capabilities:
            raise ValueError("agent and capability expectations must not be empty")
        return self


class _FirmwareExpected(ContractModel):
    platform: str = Field(min_length=1)
    components: list[str]
    templates: list[str]

    @field_validator("platform", mode="before")
    @classmethod
    def strip_platform(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("components", "templates", mode="before")
    @classmethod
    def normalize_lists(cls, value: object) -> object:
        return _normalize_list(value)


class _HardwareExpected(ContractModel):
    component_keywords: list[str]
    interfaces: list[str]
    constraint_keywords: list[str]

    @field_validator(
        "component_keywords",
        "interfaces",
        "constraint_keywords",
        mode="before",
    )
    @classmethod
    def normalize_lists(cls, value: object) -> object:
        return _normalize_list(value)


class _PCBExpected(ContractModel):
    rules: list[str]
    issue_ids: list[str]
    severities: dict[str, str]

    @field_validator("rules", "issue_ids", mode="before")
    @classmethod
    def normalize_lists(cls, value: object) -> object:
        return _normalize_list(value)


class _DebugExpected(ContractModel):
    error_type: str = Field(min_length=1)
    finding_ids: list[str]
    recommendation_keywords: list[str]

    @field_validator("error_type", mode="before")
    @classmethod
    def strip_error_type(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("finding_ids", "recommendation_keywords", mode="before")
    @classmethod
    def normalize_lists(cls, value: object) -> object:
        return _normalize_list(value)


class _KnowledgeExpected(ContractModel):
    ranked_ids: list[str]
    sources: dict[str, str]

    @field_validator("ranked_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> object:
        return _normalize_list(value)

    @model_validator(mode="after")
    def validate_contract(self) -> "_KnowledgeExpected":
        if not self.ranked_ids:
            raise ValueError("knowledge ranked ids must not be empty")
        ranked = {identifier.casefold() for identifier in self.ranked_ids}
        if any(identifier.strip().casefold() not in ranked for identifier in self.sources):
            raise ValueError("knowledge source ids must be ranked ids")
        return self


_EXPECTED_MODELS = {
    "routing": _AgentChainExpected,
    "firmware": _FirmwareExpected,
    "hardware": _HardwareExpected,
    "pcb": _PCBExpected,
    "debug": _DebugExpected,
    "knowledge": _KnowledgeExpected,
    "end_to_end": _AgentChainExpected,
}

_TARGET_NAMES = {
    "routing": "SupervisorAgent",
    "firmware": "FirmwareAgent",
    "hardware": "HardwareAgent",
    "pcb": "PCBAgent",
    "debug": "DebugAgent",
    "knowledge": "KnowledgeGateway",
    "end_to_end": "SupervisorAgent",
}


def _casefold_set(values: Sequence[str]) -> set[str]:
    return {value.strip().casefold() for value in values}


def _selection_accuracy(expected: Sequence[str], actual: Sequence[str]) -> float:
    return float(_casefold_set(expected) == _casefold_set(actual))


def _agent_envelope(result: object, expected_name: str):
    from embedded_copilot.agents.types import AgentResult, AgentStatus

    if not isinstance(result, AgentResult):
        raise TypeError("invalid agent envelope")
    validated = AgentResult.model_validate(result.model_dump(mode="python"))
    if validated.status is not AgentStatus.SUCCESS:
        raise ValueError("agent execution failed")
    if validated.agent_name.casefold() != expected_name.casefold():
        raise ValueError("agent identity does not match benchmark target")
    return validated


class BenchmarkEvaluator:
    def evaluate(
        self,
        case: BenchmarkCase,
        result: object,
        trace: BenchmarkTrace | None = None,
    ) -> BenchmarkResult:
        try:
            validated_case = BenchmarkCase.model_validate(
                case.model_dump(mode="python")
            )
            expected_model = _EXPECTED_MODELS[validated_case.category]
            try:
                expected = expected_model.model_validate(validated_case.expected)
            except Exception:
                raise BenchmarkEvaluationError(
                    "benchmark expected contract is invalid"
                ) from None
            metrics = self._evaluate_category(
                validated_case,
                expected,
                result,
                trace,
            )
            score = ScoreAggregator.aggregate(list(metrics.values()))
            errors = [
                f"metric below required score: {name}"
                for name, value in metrics.items()
                if value != 1.0
            ]
            return BenchmarkResult(
                case_id=validated_case.id,
                success=not errors,
                score=score,
                metrics=metrics,
                errors=errors,
                metadata={
                    "category": validated_case.category,
                    "target_name": _TARGET_NAMES[validated_case.category],
                },
            )
        except BenchmarkEvaluationError:
            raise
        except Exception:
            raise BenchmarkEvaluationError(
                "benchmark target output is invalid"
            ) from None

    def _evaluate_category(
        self,
        case: BenchmarkCase,
        expected: ContractModel,
        result: object,
        trace: BenchmarkTrace | None,
    ) -> dict[str, float]:
        if case.category == "routing":
            return self._routing(expected, result)
        if case.category == "firmware":
            return self._firmware(expected, result)
        if case.category == "hardware":
            return self._hardware(expected, result)
        if case.category == "pcb":
            return self._pcb(expected, result)
        if case.category == "debug":
            return self._debug(expected, result)
        if case.category == "knowledge":
            return self._knowledge(expected, result)
        return self._end_to_end(expected, result, trace)

    @staticmethod
    def _supervisor_data(result: object):
        from embedded_copilot.supervisor.models import SupervisorPlan, SupervisorResult

        envelope = _agent_envelope(result, "SupervisorAgent")
        plan = SupervisorPlan.model_validate(envelope.metadata.get("supervisor_plan"))
        report = SupervisorResult.model_validate_json(envelope.output)
        return plan, report

    @classmethod
    def _routing(cls, expected: ContractModel, result: object) -> dict[str, float]:
        assert isinstance(expected, _AgentChainExpected)
        plan, _ = cls._supervisor_data(result)
        actual = [task.agent_name for task in plan.tasks]
        return {
            "agent_selection_accuracy": _selection_accuracy(expected.agents, actual),
            "capability_coverage": CapabilityCoverageMetric.compute(
                expected.capabilities,
                actual,
            ),
        }

    @staticmethod
    def _firmware(expected: ContractModel, result: object) -> dict[str, float]:
        from embedded_copilot.firmware.project.models import FirmwareProject

        assert isinstance(expected, _FirmwareExpected)
        envelope = _agent_envelope(result, "FirmwareAgent")
        project = FirmwareProject.model_validate_json(envelope.output)
        components = project.metadata.get("components", [])
        peripherals = project.metadata.get("peripherals", [])
        if not isinstance(components, list) or not isinstance(peripherals, list):
            raise TypeError("invalid firmware metadata")
        return {
            "platform_accuracy": AccuracyMetric.compute(
                expected.platform, project.platform
            ),
            "component_coverage": CoverageMetric.compute(
                expected.components,
                [*components, *peripherals],
                substring=False,
            ),
            "template_coverage": CoverageMetric.compute(
                expected.templates,
                [entry.path for entry in project.files],
                substring=False,
            ),
        }

    @staticmethod
    def _hardware(expected: ContractModel, result: object) -> dict[str, float]:
        from embedded_copilot.hardware.models import HardwarePlan

        assert isinstance(expected, _HardwareExpected)
        envelope = _agent_envelope(result, "HardwareAgent")
        plan = HardwarePlan.model_validate_json(envelope.output)
        return {
            "component_keyword_accuracy": CoverageMetric.compute(
                expected.component_keywords,
                [component.name for component in plan.components],
                substring=True,
            ),
            "interface_accuracy": CoverageMetric.compute(
                expected.interfaces,
                plan.interfaces,
                substring=False,
            ),
            "constraint_coverage": CoverageMetric.compute(
                expected.constraint_keywords,
                plan.constraints,
                substring=True,
            ),
        }

    @staticmethod
    def _pcb(expected: ContractModel, result: object) -> dict[str, float]:
        from embedded_copilot.pcb.models import PCBReviewReport

        assert isinstance(expected, _PCBExpected)
        envelope = _agent_envelope(result, "PCBAgent")
        report = PCBReviewReport.model_validate_json(envelope.output)
        issue_ids = [issue.id for issue in report.issues]
        severity_matches = 0
        actual_severities = {
            issue.id.casefold(): issue.severity.casefold() for issue in report.issues
        }
        for issue_id, severity in expected.severities.items():
            severity_matches += (
                actual_severities.get(issue_id.strip().casefold())
                == severity.strip().casefold()
            )
        severity_accuracy = (
            severity_matches / len(expected.severities)
            if expected.severities
            else 1.0
        )
        return {
            "rule_coverage": CoverageMetric.compute(
                expected.rules,
                [*report.passed_rules, *issue_ids],
                substring=False,
            ),
            "issue_coverage": CoverageMetric.compute(
                expected.issue_ids,
                issue_ids,
                substring=False,
            ),
            "severity_accuracy": severity_accuracy,
        }

    @staticmethod
    def _debug(expected: ContractModel, result: object) -> dict[str, float]:
        from embedded_copilot.debug.models import DebugReport

        assert isinstance(expected, _DebugExpected)
        envelope = _agent_envelope(result, "DebugAgent")
        report = DebugReport.model_validate_json(envelope.output)
        return {
            "error_type_accuracy": AccuracyMetric.compute(
                expected.error_type, report.error_type
            ),
            "finding_coverage": CoverageMetric.compute(
                expected.finding_ids,
                [finding.id for finding in report.findings],
                substring=False,
            ),
            "recommendation_coverage": CoverageMetric.compute(
                expected.recommendation_keywords,
                report.recommendations,
                substring=True,
            ),
        }

    @staticmethod
    def _knowledge(expected: ContractModel, result: object) -> dict[str, float]:
        from embedded_copilot.knowledge.models import KnowledgeResult

        assert isinstance(expected, _KnowledgeExpected)
        if not isinstance(result, list):
            raise TypeError("invalid knowledge results")
        documents = [
            KnowledgeResult.model_validate(document.model_dump(mode="python"))
            for document in result
            if isinstance(document, KnowledgeResult)
        ]
        if len(documents) != len(result):
            raise TypeError("invalid knowledge result")
        expected_ids = [value.casefold() for value in expected.ranked_ids]
        actual_ids = [document.id.casefold() for document in documents]
        expected_set = set(expected_ids)
        hit_positions = [
            index for index, identifier in enumerate(actual_ids, start=1)
            if identifier in expected_set
        ]
        top_k = actual_ids[: len(expected_ids)]
        source_matches = 0
        sources_by_id = {
            document.id.casefold(): document.source.value.casefold()
            for document in documents
        }
        for identifier, source in expected.sources.items():
            source_matches += (
                sources_by_id.get(identifier.strip().casefold())
                == source.strip().casefold()
            )
        return {
            "retrieval_hit_rate": float(bool(hit_positions)),
            "source_accuracy": (
                source_matches / len(expected.sources) if expected.sources else 1.0
            ),
            "ranking_accuracy": sum(
                index < len(actual_ids) and actual_ids[index] == identifier
                for index, identifier in enumerate(expected_ids)
            )
            / len(expected_ids),
            "recall_at_k": len(expected_set.intersection(top_k)) / len(expected_set),
            "mrr": 1.0 / hit_positions[0] if hit_positions else 0.0,
        }

    @classmethod
    def _end_to_end(
        cls,
        expected: ContractModel,
        result: object,
        trace: BenchmarkTrace | None,
    ) -> dict[str, float]:
        assert isinstance(expected, _AgentChainExpected)
        if trace is None:
            raise TypeError("end-to-end evaluation requires trace")
        validated_trace = BenchmarkTrace.model_validate(trace.model_dump(mode="python"))
        plan, report = cls._supervisor_data(result)
        actual = [task.agent_name for task in plan.tasks]
        expected_pairs = list(zip(expected.agents, expected.agents[1:]))
        observed_handoffs = {
            (
                event.handoff_from.casefold(),
                event.handoff_to.casefold(),
            ): event.status
            for event in validated_trace.events
            if event.event_type == "handoff"
            and event.handoff_from is not None
            and event.handoff_to is not None
        }
        handoff_success = (
            sum(
                observed_handoffs.get((source.casefold(), target.casefold()))
                == "success"
                for source, target in expected_pairs
            )
            / len(expected_pairs)
            if expected_pairs
            else 1.0
        )
        return {
            "agent_selection_accuracy": _selection_accuracy(expected.agents, actual),
            "capability_coverage": CapabilityCoverageMetric.compute(
                expected.capabilities,
                actual,
            ),
            "pipeline_completion": CoverageMetric.compute(
                expected.agents,
                report.completed,
                substring=False,
            ),
            "handoff_success": handoff_success,
        }
