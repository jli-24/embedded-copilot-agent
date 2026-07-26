from __future__ import annotations

from embedded_copilot.context_runtime.contracts import (
    ComponentContextCandidate,
    ContextDocumentType,
    ContextImageType,
    DatasheetContext,
    FileContext,
    InterfaceContextCandidate,
    VisionContext,
)
from embedded_copilot.reasoning_runtime import SourceType
from embedded_copilot.reasoning_runtime.rules import (
    RuleContext,
    evaluate_rules,
    project_risks,
)


def _full_context() -> RuleContext:
    return RuleContext(
        reference_ids=("file:one", "file:two", "file:source", "image:1"),
        source_types=(
            SourceType.DATASHEET,
            SourceType.DATASHEET,
            SourceType.FILE,
            SourceType.VISION,
        ),
        datasheet_candidates=(
            DatasheetContext(
                file_id="file:one",
                component_candidate=None,
                interfaces=(InterfaceContextCandidate(name="SPI"),),
            ),
            DatasheetContext(
                file_id="file:two",
                component_candidate=ComponentContextCandidate(family="ESP32"),
            ),
        ),
        file_summaries=(
            FileContext(
                file_id="file:one",
                document_type=ContextDocumentType.PDF,
                page_count=10,
            ),
            FileContext(
                file_id="file:two",
                document_type=ContextDocumentType.PDF,
                page_count=20,
            ),
            FileContext(
                file_id="file:source",
                document_type=ContextDocumentType.SOURCE_CODE,
                line_count=40,
                character_count=400,
            ),
        ),
        vision_refs=(
            VisionContext(
                reference_id="image:1",
                image_type=ContextImageType.UNKNOWN,
            ),
        ),
    )


def test_rule_engine_is_stable_and_records_inactive_rules() -> None:
    context = _full_context()

    first = evaluate_rules(context)
    second = evaluate_rules(context)

    assert first == second
    assert tuple(item.rule_id for item in first) == (
        "missing_context",
        "missing_component_candidate",
        "multiple_component_candidates",
        "interface_review_required",
        "firmware_configuration_review_required",
        "visual_observation_review_required",
    )
    assert tuple(item.triggered for item in first) == (
        False,
        True,
        False,
        True,
        True,
        True,
    )
    assert all(item.rule_version == "1.0" for item in first)


def test_risk_projection_has_stable_categories_and_supporting_sources() -> None:
    context = _full_context()
    risks = project_risks(context, evaluate_rules(context))

    assert tuple(item.category for item in risks) == (
        "component_identity",
        "interface_compatibility",
        "firmware_configuration",
        "visual_interpretation",
    )
    assert risks[0].supporting_references[0].reference_id == "file:one"
    assert risks[0].supporting_references[0].source_type is SourceType.DATASHEET
    assert risks[-1].supporting_references[0].source_type is SourceType.VISION


def test_empty_context_produces_only_context_completeness_risk() -> None:
    context = RuleContext(
        reference_ids=(),
        source_types=(),
        datasheet_candidates=(),
        file_summaries=(),
        vision_refs=(),
    )

    risks = project_risks(context, evaluate_rules(context))

    assert tuple(item.category for item in risks) == ("context_completeness",)
    assert risks[0].severity == "high"
    assert risks[0].supporting_references == ()
