import pytest
from pydantic import ValidationError

from embedded_copilot.debug.models import (
    DebugEvidence,
    DebugFinding,
    DebugPlan,
    DebugReport,
    DebugRequest,
    DebugValidationResult,
)


def _finding(identifier: str = "finding-1") -> DebugFinding:
    return DebugFinding(
        id=identifier,
        category=" runtime ",
        severity=" warning ",
        description=" Observed reset signature. ",
        evidence=[" reset ", "RESET", " watchdog "],
        recommendation=" Inspect reset reason. ",
    )


def test_models_strip_strings_and_stably_deduplicate_lists() -> None:
    request = DebugRequest(
        input="  Guru Meditation reboot  ",
        project_name="  demo  ",
        platform=" ESP32 ",
        error_type=" runtime_crash ",
        logs=[" reset ", "RESET", " exception "],
    )
    evidence = DebugEvidence(
        source=" LOCAL:doc ",
        content=" knowledge body ",
        category=" runtime ",
    )
    plan = DebugPlan(
        project_name=" demo ",
        platform=" ESP32 ",
        error_type=" runtime_crash ",
        findings=[_finding()],
        actions=[" Inspect reset reason. ", "inspect reset reason."],
        rationale=" rule based ",
    )

    assert request.input == "Guru Meditation reboot"
    assert request.project_name == "demo"
    assert request.platform == "ESP32"
    assert request.error_type == "runtime_crash"
    assert request.logs == ["reset", "exception"]
    assert evidence.source == "LOCAL:doc"
    assert plan.actions == ["Inspect reset reason."]
    assert plan.platform == "ESP32"
    assert plan.error_type == "runtime_crash"
    assert plan.findings[0].evidence == ["reset", "watchdog"]


def test_models_are_frozen_and_forbid_extra_fields() -> None:
    request = DebugRequest(input="error: failed", error_type="compile_error")

    with pytest.raises(ValidationError):
        request.input = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        DebugEvidence(
            source="LOCAL:doc",
            content="body",
            category="compile",
            extra=True,  # type: ignore[call-arg]
        )


@pytest.mark.parametrize("model", ["plan", "report"])
def test_plan_and_report_reject_duplicate_finding_ids(model: str) -> None:
    findings = [_finding("Duplicate"), _finding(" duplicate ")]

    with pytest.raises(ValidationError, match="duplicate debug finding"):
        if model == "plan":
            DebugPlan(
                project_name="demo",
                error_type="runtime_crash",
                findings=findings,
                actions=["inspect"],
                rationale="rules",
            )
        else:
            DebugReport(
                project_name="demo",
                error_type="runtime_crash",
                summary="summary",
                findings=findings,
                recommendations=["inspect"],
            )


def test_request_rejects_noncanonical_platform_and_error_type() -> None:
    with pytest.raises(ValidationError):
        DebugRequest(input="failure", platform="ESP-IDF")
    with pytest.raises(ValidationError):
        DebugRequest(input="failure", error_type="unknown")


def test_finding_rejects_noncanonical_severity() -> None:
    with pytest.raises(ValidationError):
        _finding().model_copy(update={"severity": "fatal"}).__class__(
            **{
                **_finding().model_dump(mode="python"),
                "severity": "fatal",
            }
        )


def test_validation_result_enforces_success_error_invariant() -> None:
    assert DebugValidationResult(success=True).errors == []
    with pytest.raises(ValidationError):
        DebugValidationResult(success=True, errors=["bad"])
    with pytest.raises(ValidationError):
        DebugValidationResult(success=False)
