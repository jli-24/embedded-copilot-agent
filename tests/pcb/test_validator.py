from embedded_copilot.pcb.models import PCBIssue, PCBReviewReport
from embedded_copilot.pcb.validator import PCBValidator


def _issue(**updates: object) -> PCBIssue:
    payload: dict[str, object] = {
        "id": "pcb-ground-integrity",
        "category": "ground",
        "severity": "warning",
        "description": "Ground evidence is missing.",
        "recommendation": "Confirm ground integrity.",
        "evidence": ["No GND declaration was provided."],
    }
    payload.update(updates)
    return PCBIssue.model_construct(**payload)


def _report(**updates: object) -> PCBReviewReport:
    payload: dict[str, object] = {
        "project_name": "demo",
        "platform": "ESP32",
        "issues": [_issue()],
        "passed_rules": [],
        "warnings": ["Unverified"],
        "summary": "Deterministic review.",
        "metadata": {},
    }
    payload.update(updates)
    return PCBReviewReport.model_construct(**payload)


def test_validator_accepts_structurally_valid_report_with_design_issues() -> None:
    result = PCBValidator().validate(_report())

    assert result.success is True
    assert result.errors == []


def test_validator_rejects_empty_report() -> None:
    result = PCBValidator().validate(
        _report(issues=[], passed_rules=[], warnings=[])
    )

    assert result.success is False
    assert "PCB review report must not be empty" in result.errors


def test_validator_rejects_invalid_issue_severity_and_empty_evidence() -> None:
    result = PCBValidator().validate(
        _report(issues=[_issue(severity="critical", evidence=[])])
    )

    assert result.success is False
    assert "unsupported PCB issue severity: critical" in result.errors
    assert "PCB issue evidence must not be empty: pcb-ground-integrity" in result.errors


def test_validator_rejects_duplicate_issue_ids_case_insensitively() -> None:
    result = PCBValidator().validate(
        _report(
            issues=[
                _issue(id="pcb-ground-integrity"),
                _issue(id="PCB-GROUND-INTEGRITY"),
            ]
        )
    )

    assert result.success is False
    assert "duplicate PCB issue id: PCB-GROUND-INTEGRITY" in result.errors


def test_validator_rejects_duplicate_passed_rules_and_warnings() -> None:
    result = PCBValidator().validate(
        _report(
            issues=[],
            passed_rules=["pcb-ground-integrity", "PCB-GROUND-INTEGRITY"],
            warnings=["Unverified", "unverified"],
        )
    )

    assert result.success is False
    assert "duplicate PCB passed rule: PCB-GROUND-INTEGRITY" in result.errors
    assert "duplicate PCB warning: unverified" in result.errors
