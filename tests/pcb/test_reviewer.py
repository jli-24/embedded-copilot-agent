from embedded_copilot.hardware.models import HardwareComponent, HardwarePlan
from embedded_copilot.pcb.analyzer import PCBRequirementAnalyzer
from embedded_copilot.pcb.knowledge import PCBRuleDocument
from embedded_copilot.pcb.models import PCBRequirement, PCBRuleEvaluation
from embedded_copilot.pcb.reviewer import PCBReviewer
from embedded_copilot.pcb.rules import PCBRuleEngine


def _document() -> PCBRuleDocument:
    return PCBRuleDocument(
        id="ground-rule",
        title="Authorized Ground Review Notes",
        category="ground",
        content="Private authorized rule content.",
        metadata={"license": "test"},
    )


def test_reviewer_preserves_document_and_records_provenance() -> None:
    requirement = PCBRequirement(project_name="demo", components=["MCU"])
    document = _document()
    original = document.model_dump(mode="json")
    evaluation = PCBRuleEngine().evaluate(requirement)

    report = PCBReviewer().review(requirement, [document], evaluation=evaluation)

    assert "Authorized Ground Review Notes (ground-rule)" in report.summary
    assert report.metadata["evidence_document_ids"] == ["ground-rule"]
    assert report.metadata["review_mode"] == "deterministic_unverified"
    assert document.model_dump(mode="json") == original


def test_reviewer_marks_empty_knowledge_as_generic_and_unverified() -> None:
    requirement = PCBRequirement(project_name="demo", components=["Power"])

    report = PCBReviewer().review(requirement, [])

    assert "no PCB knowledge documents" in report.summary
    assert any("generic" in warning for warning in report.warnings)
    assert any("unverified" in warning for warning in report.warnings)


class _MustNotRunRuleEngine:
    def evaluate(self, requirement):
        raise AssertionError("explicit evaluation must be used")


def test_reviewer_uses_explicit_rule_evaluation_when_supplied() -> None:
    evaluation = PCBRuleEvaluation(issues=[], passed_rules=["explicit-rule"])
    reviewer = PCBReviewer(rule_engine=_MustNotRunRuleEngine())

    report = reviewer.review(
        PCBRequirement(project_name="demo"),
        [],
        evaluation=evaluation,
    )

    assert report.passed_rules == ["explicit-rule"]


def test_review_hardware_plan_uses_same_rules_without_mutation() -> None:
    plan = HardwarePlan(
        project_name="camera_board",
        platform="ESP32",
        mcu="ESP32-S3",
        components=[
            HardwareComponent(
                name="Power stage",
                category="power",
                description="Unverified",
            )
        ],
        constraints=["Decoupling and GND integrity are declared."],
        rationale="Unverified",
    )
    original = plan.model_dump(mode="json")
    reviewer = PCBReviewer(analyzer=PCBRequirementAnalyzer())

    report = reviewer.review_hardware_plan(plan)

    assert report.project_name == "camera_board"
    assert report.issues == []
    assert plan.model_dump(mode="json") == original
