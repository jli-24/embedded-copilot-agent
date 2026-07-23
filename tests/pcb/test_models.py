import pytest
from pydantic import ValidationError

from embedded_copilot.pcb.models import (
    PCBIssue,
    PCBRequirement,
    PCBReviewReport,
    PCBRuleEvaluation,
    PCBValidationResult,
)


def test_pcb_models_strip_and_stably_deduplicate_lists() -> None:
    requirement = PCBRequirement(
        project_name=" demo ",
        platform=" ESP32 ",
        components=[" MCU ", "mcu", "Camera"],
        interfaces=[" SPI ", "spi", "I2C"],
        constraints=[" Keep GND intact ", "keep gnd intact"],
    )
    issue = PCBIssue(
        id=" power-decoupling-unverified ",
        category=" power ",
        severity=" warning ",
        description=" Missing evidence ",
        recommendation=" Confirm decoupling ",
        evidence=[" No declaration ", "no declaration"],
    )
    report = PCBReviewReport(
        project_name=" demo ",
        platform=" ESP32 ",
        issues=[issue],
        passed_rules=[" power-declaration ", "POWER-DECLARATION"],
        warnings=[" Unverified ", "unverified"],
        summary=" Review summary ",
    )

    assert requirement.project_name == "demo"
    assert requirement.components == ["MCU", "Camera"]
    assert requirement.interfaces == ["SPI", "I2C"]
    assert issue.id == "power-decoupling-unverified"
    assert issue.evidence == ["No declaration"]
    assert report.passed_rules == ["power-declaration"]
    assert report.warnings == ["Unverified"]


def test_pcb_models_are_frozen_and_forbid_extra_fields() -> None:
    requirement = PCBRequirement(project_name="demo")

    with pytest.raises(ValidationError):
        requirement.project_name = "changed"
    with pytest.raises(ValidationError):
        PCBRequirement(project_name="demo", unsupported=True)


def test_rule_evaluation_and_validation_result_contracts() -> None:
    evaluation = PCBRuleEvaluation(
        issues=[],
        passed_rules=[" ground-integrity ", "GROUND-INTEGRITY"],
    )

    assert evaluation.passed_rules == ["ground-integrity"]
    assert PCBValidationResult(success=True).errors == []
    with pytest.raises(ValidationError):
        PCBValidationResult(success=True, errors=["unexpected"])
    with pytest.raises(ValidationError):
        PCBValidationResult(success=False)
