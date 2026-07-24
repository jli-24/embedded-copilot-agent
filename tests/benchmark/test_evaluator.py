from __future__ import annotations

import pytest

from embedded_copilot.agents.types import AgentResult, AgentStatus
from embedded_copilot.benchmark.evaluator import BenchmarkEvaluator
from embedded_copilot.benchmark.exceptions import BenchmarkEvaluationError
from embedded_copilot.benchmark.models import (
    BenchmarkCase,
    BenchmarkTrace,
    ExecutionMetrics,
    TraceEvent,
)
from embedded_copilot.debug.models import DebugFinding, DebugReport
from embedded_copilot.firmware.project.models import FirmwareProject, ProjectFile
from embedded_copilot.hardware.models import HardwareComponent, HardwarePlan
from embedded_copilot.knowledge.models import (
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.pcb.models import PCBIssue, PCBReviewReport
from embedded_copilot.supervisor.models import (
    AgentInvocation,
    SupervisorPlan,
    SupervisorResult,
)


def _case(category: str, expected: dict[str, object]) -> BenchmarkCase:
    return BenchmarkCase(
        id=f"{category}-case",
        name=f"{category} case",
        category=category,
        input="synthetic benchmark request",
        expected=expected,
    )


def _agent(name: str, output: str, **metadata: object) -> AgentResult:
    return AgentResult(
        agent_name=name,
        status=AgentStatus.SUCCESS,
        output=output,
        metadata=metadata,
    )


def _supervisor_result() -> AgentResult:
    plan = SupervisorPlan(
        project_name="synthetic",
        tasks=[
            AgentInvocation(agent_name="FirmwareAgent", task="firmware"),
            AgentInvocation(agent_name="HardwareAgent", task="hardware"),
            AgentInvocation(agent_name="PCBAgent", task="pcb"),
        ],
        rationale="synthetic deterministic chain",
    )
    report = SupervisorResult(
        project_name="synthetic",
        completed=["FirmwareAgent", "HardwareAgent", "PCBAgent"],
        results={
            "FirmwareAgent": {},
            "HardwareAgent": {},
            "PCBAgent": {},
        },
        summary="synthetic pipeline complete",
    )
    return _agent(
        "SupervisorAgent",
        report.model_dump_json(),
        supervisor_plan=plan.model_dump(mode="json"),
        agent_results=[],
    )


def test_evaluator_scores_routing_and_capability_coverage() -> None:
    case = _case(
        "routing",
        {
            "agents": ["FirmwareAgent", "HardwareAgent", "PCBAgent"],
            "capabilities": ["firmware", "hardware", "pcb", "debug"],
        },
    )

    result = BenchmarkEvaluator().evaluate(case, _supervisor_result())

    assert result.success is False
    assert result.score == 0.875
    assert result.metrics == {
        "agent_selection_accuracy": 1.0,
        "capability_coverage": 0.75,
    }
    assert result.metadata == {
        "category": "routing",
        "target_name": "SupervisorAgent",
    }


def test_evaluator_scores_firmware_hardware_pcb_and_debug_outputs() -> None:
    firmware = FirmwareProject(
        name="synthetic",
        platform="ESP32",
        files=[ProjectFile(path="main/main.c", content="", language="C")],
        metadata={"components": ["camera"], "peripherals": ["I2C"]},
    )
    hardware = HardwarePlan(
        project_name="synthetic",
        platform="ESP32",
        mcu="ESP32-S3",
        components=[
            HardwareComponent(
                name="Synthetic camera module",
                category="sensor",
                interface=["I2C"],
                description="fixture",
            )
        ],
        interfaces=["I2C"],
        constraints=["3.3V logic"],
        rationale="synthetic",
    )
    issue = PCBIssue(
        id="PCB-POWER-001",
        category="power",
        severity="warning",
        description="synthetic issue",
        recommendation="synthetic recommendation",
        evidence=["synthetic observation"],
    )
    pcb = PCBReviewReport(
        project_name="synthetic",
        issues=[issue],
        passed_rules=["PCB-DECOUPLING-001"],
        summary="synthetic review",
    )
    finding = DebugFinding(
        id="DBG-COMPILE-MISSING-INCLUDE",
        category="compile",
        severity="error",
        description="observed synthetic missing include",
        evidence=["synthetic compiler marker"],
        recommendation="Check the include path",
    )
    debug = DebugReport(
        project_name="synthetic",
        platform="ESP32",
        error_type="compile_error",
        summary="synthetic debug report",
        findings=[finding],
        recommendations=["Check the include path"],
    )

    cases_and_results = [
        (
            _case(
                "firmware",
                {
                    "platform": "esp32",
                    "components": ["camera", "i2c"],
                    "templates": ["main/main.c"],
                },
            ),
            _agent("FirmwareAgent", firmware.model_dump_json()),
        ),
        (
            _case(
                "hardware",
                {
                    "component_keywords": ["camera"],
                    "interfaces": ["i2c"],
                    "constraint_keywords": ["3.3v"],
                },
            ),
            _agent("HardwareAgent", hardware.model_dump_json()),
        ),
        (
            _case(
                "pcb",
                {
                    "rules": ["PCB-DECOUPLING-001"],
                    "issue_ids": ["PCB-POWER-001"],
                    "severities": {"PCB-POWER-001": "warning"},
                },
            ),
            _agent("PCBAgent", pcb.model_dump_json()),
        ),
        (
            _case(
                "debug",
                {
                    "error_type": "compile_error",
                    "finding_ids": ["DBG-COMPILE-MISSING-INCLUDE"],
                    "recommendation_keywords": ["include path"],
                },
            ),
            _agent("DebugAgent", debug.model_dump_json()),
        ),
    ]

    for case, agent_result in cases_and_results:
        evaluated = BenchmarkEvaluator().evaluate(case, agent_result)
        assert evaluated.success is True
        assert evaluated.score == 1.0


def test_evaluator_scores_all_knowledge_ranking_metrics() -> None:
    case = _case(
        "knowledge",
        {
            "ranked_ids": ["doc-a", "doc-b"],
            "sources": {"doc-a": "LOCAL", "doc-b": "GITHUB"},
        },
    )
    results = [
        KnowledgeResult(
            id="doc-b",
            title="Synthetic B",
            content="synthetic content",
            source=KnowledgeSource.GITHUB,
            score=1.0,
        ),
        KnowledgeResult(
            id="doc-a",
            title="Synthetic A",
            content="synthetic content",
            source=KnowledgeSource.LOCAL,
            score=0.9,
        ),
    ]

    evaluated = BenchmarkEvaluator().evaluate(case, results)

    assert evaluated.metrics == {
        "retrieval_hit_rate": 1.0,
        "source_accuracy": 1.0,
        "ranking_accuracy": 0.0,
        "recall_at_k": 1.0,
        "mrr": 1.0,
    }
    assert evaluated.score == 0.8
    assert evaluated.success is False
    assert "synthetic content" not in evaluated.model_dump_json()


def test_evaluator_scores_end_to_end_completion_and_handoff() -> None:
    case = _case(
        "end_to_end",
        {
            "agents": ["FirmwareAgent", "HardwareAgent", "PCBAgent"],
            "capabilities": ["firmware", "hardware", "pcb"],
        },
    )
    trace = BenchmarkTrace(
        case_id=case.id,
        events=[
            TraceEvent(sequence=1, event_type="agent_call", target="FirmwareAgent", status="success"),
            TraceEvent(
                sequence=2,
                event_type="handoff",
                target="HardwareAgent",
                status="success",
                handoff_from="FirmwareAgent",
                handoff_to="HardwareAgent",
            ),
            TraceEvent(sequence=3, event_type="agent_call", target="HardwareAgent", status="success"),
            TraceEvent(
                sequence=4,
                event_type="handoff",
                target="PCBAgent",
                status="success",
                handoff_from="HardwareAgent",
                handoff_to="PCBAgent",
            ),
            TraceEvent(sequence=5, event_type="agent_call", target="PCBAgent", status="success"),
        ],
        execution_metrics=ExecutionMetrics(
            execution_time_ms=1,
            agent_calls=3,
            knowledge_calls=0,
        ),
    )

    evaluated = BenchmarkEvaluator().evaluate(
        case,
        _supervisor_result(),
        trace=trace,
    )

    assert evaluated.success is True
    assert evaluated.metrics == {
        "agent_selection_accuracy": 1.0,
        "capability_coverage": 1.0,
        "pipeline_completion": 1.0,
        "handoff_success": 1.0,
    }


@pytest.mark.parametrize(
    "expected",
    [
        {"agents": ["FirmwareAgent"]},
        {
            "agents": ["FirmwareAgent"],
            "capabilities": ["firmware"],
            "extra": True,
        },
    ],
)
def test_evaluator_rejects_invalid_exact_expected_contract(
    expected: dict[str, object],
) -> None:
    with pytest.raises(BenchmarkEvaluationError, match="expected contract"):
        BenchmarkEvaluator().evaluate(_case("routing", expected), _supervisor_result())


def test_evaluator_rejects_error_or_malformed_target_output_safely() -> None:
    case = _case(
        "debug",
        {
            "error_type": "compile_error",
            "finding_ids": [],
            "recommendation_keywords": [],
        },
    )
    error = AgentResult(
        agent_name="DebugAgent",
        status=AgentStatus.ERROR,
        output="PRIVATE_SENTINEL C:/private/log.txt",
    )

    with pytest.raises(BenchmarkEvaluationError, match="target output is invalid") as captured:
        BenchmarkEvaluator().evaluate(case, error)

    assert "PRIVATE_SENTINEL" not in str(captured.value)
    assert "private" not in str(captured.value)


def test_evaluator_rejects_mismatched_agent_identity() -> None:
    firmware = FirmwareProject(
        name="synthetic",
        platform="ESP32",
        files=[ProjectFile(path="main/main.c", content="", language="C")],
        metadata={"components": [], "peripherals": []},
    )
    case = _case(
        "firmware",
        {"platform": "ESP32", "components": [], "templates": ["main/main.c"]},
    )

    with pytest.raises(BenchmarkEvaluationError, match="target output is invalid"):
        BenchmarkEvaluator().evaluate(
            case,
            _agent("DebugAgent", firmware.model_dump_json()),
        )


def test_evaluator_normalizes_tuple_expected_string_lists() -> None:
    case = _case(
        "routing",
        {
            "agents": (" FirmwareAgent ", "firmwareagent", "HardwareAgent"),
            "capabilities": (" firmware ", "FIRMWARE", "hardware"),
        },
    )
    plan = SupervisorPlan(
        project_name="synthetic",
        tasks=[
            AgentInvocation(agent_name="FirmwareAgent", task="firmware"),
            AgentInvocation(agent_name="HardwareAgent", task="hardware"),
        ],
        rationale="synthetic",
    )
    report = SupervisorResult(
        project_name="synthetic",
        completed=["FirmwareAgent", "HardwareAgent"],
        results={"FirmwareAgent": {}, "HardwareAgent": {}},
        summary="synthetic",
    )

    evaluated = BenchmarkEvaluator().evaluate(
        case,
        _agent(
            "SupervisorAgent",
            report.model_dump_json(),
            supervisor_plan=plan.model_dump(mode="json"),
        ),
    )

    assert evaluated.success is True
