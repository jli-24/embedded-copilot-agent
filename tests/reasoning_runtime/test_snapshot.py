from __future__ import annotations

import json
import unicodedata

import pytest
from pydantic import ValidationError

from embedded_copilot.context_runtime.contracts import (
    ComponentContextCandidate,
    ContextDocumentType,
    DatasheetContext,
    EngineeringContextRequest,
    EngineeringContextResponse,
    EngineeringContextSummary,
    FileContext,
    InterfaceContextCandidate,
)
from embedded_copilot.reasoning_runtime import (
    ReasoningContextConflict,
    ReasoningContextSnapshot,
    SourceType,
    build_reasoning_context_snapshot,
)
from embedded_copilot.reasoning_runtime.snapshot import canonical_snapshot_payload

CONTEXT_ID = "context:0123456789abcdef01234567"


def _request(*references: str) -> EngineeringContextRequest:
    return EngineeringContextRequest(
        session_id="session:1",
        task_intent="Review referenced engineering context.",
        reference_ids=references,
    )


def _response(request: EngineeringContextRequest) -> EngineeringContextResponse:
    datasheet = DatasheetContext(
        file_id="file:datasheet-1",
        component_candidate=ComponentContextCandidate(
            family="ESP32",
            model="ESP32-S3",
        ),
        interfaces=(InterfaceContextCandidate(name="I2C"),),
    )
    return EngineeringContextResponse(
        context_summary=EngineeringContextSummary(
            context_id=CONTEXT_ID,
            task_intent=request.task_intent,
            datasheets=(datasheet,),
            files=(
                FileContext(
                    file_id="file:datasheet-1",
                    document_type=ContextDocumentType.PDF,
                    page_count=42,
                ),
            ),
        )
    )


def test_builder_freezes_safe_context_with_stable_fingerprint() -> None:
    request = _request("file:datasheet-1")

    first = build_reasoning_context_snapshot(
        request, _response(request), expected_context_id=CONTEXT_ID
    )
    second = build_reasoning_context_snapshot(
        request, _response(request), expected_context_id=CONTEXT_ID
    )

    assert first == second
    assert first.source_types == (SourceType.DATASHEET,)
    assert first.snapshot_fingerprint.startswith("sha256:")
    assert len(first.snapshot_fingerprint) == 71


def test_snapshot_rejects_tampering_before_acceptance() -> None:
    request = _request("file:datasheet-1")
    snapshot = build_reasoning_context_snapshot(
        request, _response(request), expected_context_id=CONTEXT_ID
    )
    payload = snapshot.model_dump(mode="python")
    payload["task_intent"] = "Changed task intent."

    with pytest.raises(ValidationError, match="fingerprint"):
        ReasoningContextSnapshot.model_validate(payload)


def test_canonical_payload_has_no_null_float_or_execution_fields() -> None:
    request = _request("file:datasheet-1")
    snapshot = build_reasoning_context_snapshot(
        request, _response(request), expected_context_id=CONTEXT_ID
    )
    payload = canonical_snapshot_payload(
        schema_version=snapshot.schema_version,
        context_id=snapshot.context_id,
        task_intent=snapshot.task_intent,
        reference_ids=snapshot.reference_ids,
        source_types=snapshot.source_types,
        datasheet_candidates=snapshot.datasheet_candidates,
        file_summaries=snapshot.file_summaries,
        vision_refs=snapshot.vision_refs,
    )
    encoded = json.dumps(payload, allow_nan=False, sort_keys=True)

    assert "null" not in encoded
    assert "trace_id" not in encoded
    assert "timestamp" not in encoded
    assert "random" not in encoded
    assert not any(isinstance(value, float) for value in _walk(payload))


def test_builder_normalizes_equivalent_unicode_before_fingerprinting() -> None:
    composed = "R\u00e9view context."
    decomposed = unicodedata.normalize("NFD", composed)
    first_request = EngineeringContextRequest(
        session_id="session:1",
        task_intent=composed,
        reference_ids=(),
    )
    second_request = EngineeringContextRequest(
        session_id="session:1",
        task_intent=decomposed,
        reference_ids=(),
    )

    def empty_response(
        request: EngineeringContextRequest,
    ) -> EngineeringContextResponse:
        return EngineeringContextResponse(
            context_summary=EngineeringContextSummary(
                context_id=CONTEXT_ID,
                task_intent=request.task_intent,
            )
        )

    first = build_reasoning_context_snapshot(
        first_request, empty_response(first_request), expected_context_id=CONTEXT_ID
    )
    second = build_reasoning_context_snapshot(
        second_request, empty_response(second_request), expected_context_id=CONTEXT_ID
    )

    assert first.snapshot_fingerprint == second.snapshot_fingerprint


def test_builder_rejects_context_identity_conflict() -> None:
    request = _request("file:datasheet-1")

    with pytest.raises(ReasoningContextConflict):
        build_reasoning_context_snapshot(
            request,
            _response(request),
            expected_context_id="context:ffffffffffffffffffffffff",
        )


def _walk(value: object):
    if isinstance(value, dict):
        for item in value.values():
            yield item
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield item
            yield from _walk(item)
