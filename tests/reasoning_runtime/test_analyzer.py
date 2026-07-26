from __future__ import annotations

from embedded_copilot.context_runtime.contracts import (
    ComponentContextCandidate,
    ContextDocumentType,
    DatasheetContext,
    FileContext,
)
from embedded_copilot.reasoning_runtime.analysis import analyze_context
from embedded_copilot.reasoning_runtime.contracts import ReasoningContextSnapshot
from embedded_copilot.reasoning_runtime.contracts import SourceType
from embedded_copilot.reasoning_runtime.snapshot import snapshot_fingerprint


def _snapshot(
    datasheets: tuple[DatasheetContext, ...] = (),
) -> ReasoningContextSnapshot:
    reference_ids = tuple(item.file_id for item in datasheets)
    fields = {
        "schema_version": "1.0",
        "context_id": "context:0123456789abcdef01234567",
        "task_intent": "Review engineering context.",
        "reference_ids": reference_ids,
        "source_types": tuple(SourceType.DATASHEET for _ in reference_ids),
        "datasheet_candidates": datasheets,
        "file_summaries": tuple(
            FileContext(
                file_id=item.file_id,
                document_type=ContextDocumentType.PDF,
                page_count=1,
            )
            for item in datasheets
        ),
        "vision_refs": (),
    }
    return ReasoningContextSnapshot(
        snapshot_fingerprint=snapshot_fingerprint(**fields),
        **fields,
    )


def test_empty_context_is_low_confidence_without_fact_promotion() -> None:
    result = analyze_context(_snapshot())

    assert result.confidence == "low"
    assert result.presentation_summary is None
    assert "0 datasheet candidate" in result.summary
    assert "No referenced engineering context" in result.assumptions[-1]


def test_datasheet_candidate_is_medium_but_never_high_confidence() -> None:
    result = analyze_context(
        _snapshot(
            (
                DatasheetContext(
                    file_id="file:1",
                    component_candidate=ComponentContextCandidate(family="ESP32"),
                ),
            )
        )
    )

    assert result.confidence == "medium"
    assert "unverified candidates" in result.assumptions[1]
    assert result.confidence != "high"
