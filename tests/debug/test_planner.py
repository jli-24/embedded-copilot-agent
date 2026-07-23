import pytest

from embedded_copilot.debug.exceptions import DebugPlanningError
from embedded_copilot.debug.models import DebugEvidence, DebugFinding, DebugRequest
from embedded_copilot.debug.planner import DebugPlanner


def _request() -> DebugRequest:
    return DebugRequest(
        input="ESP32 watchdog reset",
        project_name="demo",
        platform="ESP32",
        error_type="runtime_crash",
        logs=["watchdog reset"],
    )


def _finding(identifier: str, recommendation: str) -> DebugFinding:
    return DebugFinding(
        id=identifier,
        category="runtime",
        severity="error",
        description="Observed runtime signature.",
        evidence=["watchdog reset"],
        recommendation=recommendation,
    )


def test_planner_builds_stable_actions_and_unverified_metadata() -> None:
    plan = DebugPlanner().plan(
        _request(),
        [
            _finding("one", "Inspect task blocking."),
            _finding("two", "inspect task blocking."),
        ],
        [],
    )

    assert plan.project_name == "demo"
    assert plan.actions == ["Inspect task blocking."]
    assert plan.metadata == {
        "analysis_mode": "unverified_rule_based",
        "finding_count": 2,
        "knowledge_source_count": 0,
        "knowledge_sources": [],
    }
    assert plan.rationale == (
        "Deterministic debug rules produced 2 finding(s) using 0 knowledge "
        "source(s); no knowledge evidence was retrieved."
    )


def test_planner_records_knowledge_sources_without_content() -> None:
    evidence = DebugEvidence(
        source="LOCAL:watchdog",
        content="PRIVATE_DOCUMENT_BODY",
        category="runtime",
    )

    plan = DebugPlanner().plan(
        _request(),
        [_finding("one", "Inspect task blocking.")],
        [evidence],
    )

    assert plan.metadata["analysis_mode"] == "knowledge_augmented"
    assert plan.metadata["knowledge_sources"] == ["LOCAL:watchdog"]
    assert "PRIVATE_DOCUMENT_BODY" not in plan.model_dump_json()


def test_planner_uses_default_project_name() -> None:
    request = _request().model_copy(update={"project_name": None})

    assert DebugPlanner().plan(
        request,
        [_finding("one", "Inspect task blocking.")],
        [],
    ).project_name == "debug_project"


def test_planner_rejects_empty_findings() -> None:
    with pytest.raises(DebugPlanningError, match="at least one finding"):
        DebugPlanner().plan(_request(), [], [])


def test_planner_isolates_nested_finding_metadata() -> None:
    finding = _finding("one", "Inspect task blocking.").model_copy(
        update={"metadata": {"nested": {"keep": True}}}
    )

    plan = DebugPlanner().plan(_request(), [finding], [])
    finding.metadata["nested"]["keep"] = False  # type: ignore[index]

    assert plan.findings[0].metadata == {"nested": {"keep": True}}
