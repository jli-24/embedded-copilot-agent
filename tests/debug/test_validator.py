from embedded_copilot.debug.models import DebugFinding, DebugReport
from embedded_copilot.debug.validator import DebugValidator


def _finding(
    identifier: str = "runtime-reset",
    *,
    severity: str = "error",
    evidence: list[str] | None = None,
) -> DebugFinding:
    values = {
        "id": identifier,
        "category": "runtime",
        "severity": severity,
        "description": "Observed reset signature.",
        "evidence": ["reset"] if evidence is None else evidence,
        "recommendation": "Inspect reset reason.",
        "metadata": {},
    }
    if severity not in {"info", "warning", "error", "critical"}:
        return DebugFinding.model_construct(**values)
    return DebugFinding(
        **values,
    )


def _report(findings: list[DebugFinding] | None = None) -> DebugReport:
    return DebugReport(
        project_name="demo",
        platform="ESP32",
        error_type="runtime_crash",
        summary="Deterministic report.",
        findings=[_finding()] if findings is None else findings,
        recommendations=["Inspect reset reason."],
    )


def test_validator_accepts_complete_report() -> None:
    validation = DebugValidator().validate(_report())

    assert validation.success is True
    assert validation.errors == []
    assert validation.metadata == {"finding_count": 1, "recommendation_count": 1}


def test_validator_rejects_empty_report() -> None:
    report = _report([]).model_copy(update={"recommendations": []})

    validation = DebugValidator().validate(report)

    assert validation.success is False
    assert "debug report must contain findings" in validation.errors
    assert "debug report must contain recommendations" in validation.errors


def test_validator_rejects_invalid_severity_and_missing_evidence() -> None:
    report = _report([_finding(severity="fatal", evidence=[])])

    validation = DebugValidator().validate(report)

    assert validation.success is False
    assert "unsupported debug finding severity: fatal" in validation.errors
    assert "debug finding evidence must not be empty: runtime-reset" in validation.errors


def test_validator_rejects_duplicate_finding_ids_even_for_constructed_model() -> None:
    report = DebugReport.model_construct(
        project_name="demo",
        platform="ESP32",
        error_type="runtime_crash",
        summary="summary",
        findings=[_finding("same"), _finding("SAME")],
        recommendations=["inspect"],
        metadata={},
    )

    validation = DebugValidator().validate(report)

    assert validation.success is False
    assert "duplicate debug finding id: SAME" in validation.errors


def test_validator_rejects_constructed_finding_with_missing_text_fields() -> None:
    finding = DebugFinding.model_construct(
        id="incomplete",
        category="runtime",
        severity="error",
        description="",
        evidence=["reset"],
        recommendation="",
        metadata={},
    )

    validation = DebugValidator().validate(_report([finding]))

    assert validation.success is False
    assert "debug finding description must not be empty: incomplete" in validation.errors
    assert "debug finding recommendation must not be empty: incomplete" in validation.errors


def test_validator_rejects_constructed_finding_with_absent_fields() -> None:
    finding = DebugFinding.model_construct(
        id="absent",
        category="runtime",
        severity="error",
        metadata={},
    )
    report = _report([finding]).model_copy(update={"summary": ""})

    validation = DebugValidator().validate(report)

    assert validation.success is False
    assert "debug report summary must not be empty" in validation.errors
    assert "debug finding description must not be empty: absent" in validation.errors
    assert "debug finding evidence must not be empty: absent" in validation.errors
    assert "debug finding recommendation must not be empty: absent" in validation.errors


def test_validator_rejects_fully_constructed_empty_report_and_blank_lists() -> None:
    empty_validation = DebugValidator().validate(DebugReport.model_construct())
    blank_finding = DebugFinding.model_construct(
        id="blank",
        category="runtime",
        severity="error",
        description="observed",
        evidence=[""],
        recommendation="inspect",
        metadata={},
    )
    blank_report = DebugReport.model_construct(
        project_name="demo",
        platform="ESP32",
        error_type="runtime_crash",
        summary="summary",
        findings=[blank_finding],
        recommendations=[""],
        metadata={},
    )
    blank_validation = DebugValidator().validate(blank_report)

    assert empty_validation.success is False
    assert "debug report must contain findings" in empty_validation.errors
    assert "debug report must contain recommendations" in empty_validation.errors
    assert "debug report must contain recommendations" in blank_validation.errors
    assert "debug finding evidence must not be empty: blank" in blank_validation.errors
