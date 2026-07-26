from __future__ import annotations

import copy
import hashlib
import json
import unicodedata
from typing import Any

from pydantic import ValidationError

from embedded_copilot.context_runtime.contracts import (
    DatasheetContext,
    EngineeringContextRequest,
    EngineeringContextResponse,
    FileContext,
    VisionContext,
)
from embedded_copilot.reasoning_runtime.contracts.models import (
    ReasoningContextSnapshot,
    SourceType,
)
from embedded_copilot.reasoning_runtime.exceptions import (
    ReasoningContextConflict,
    ReasoningRequestRejected,
)


def _text(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _component_payload(component: Any) -> dict[str, object]:
    payload: dict[str, object] = {
        "semantics": component.semantics,
        "family": component.family,
    }
    if component.model is not None:
        payload["model"] = _text(component.model)
    return payload


def _datasheet_payload(value: DatasheetContext) -> dict[str, object]:
    payload: dict[str, object] = {
        "candidate_semantics": value.candidate_semantics,
        "file_id": _text(value.file_id),
        "interfaces": [
            {"semantics": item.semantics, "name": item.name}
            for item in value.interfaces
        ],
        "sections": [
            {"semantics": item.semantics, "name": item.name} for item in value.sections
        ],
    }
    if value.component_candidate is not None:
        payload["component_candidate"] = _component_payload(value.component_candidate)
    return payload


def _file_payload(value: FileContext) -> dict[str, object]:
    payload: dict[str, object] = {
        "file_id": _text(value.file_id),
        "document_type": value.document_type.value,
    }
    for field in ("page_count", "line_count", "character_count"):
        item = getattr(value, field)
        if item is not None:
            if isinstance(item, bool) or not isinstance(item, int):
                raise ReasoningRequestRejected()
            payload[field] = item
    return payload


def canonical_snapshot_payload(
    *,
    schema_version: str,
    context_id: str,
    task_intent: str,
    reference_ids: tuple[str, ...],
    source_types: tuple[SourceType, ...],
    datasheet_candidates: tuple[DatasheetContext, ...],
    file_summaries: tuple[FileContext, ...],
    vision_refs: tuple[VisionContext, ...],
) -> dict[str, object]:
    return {
        "context_id": _text(context_id),
        "datasheet_candidates": [
            _datasheet_payload(item) for item in datasheet_candidates
        ],
        "file_summaries": [_file_payload(item) for item in file_summaries],
        "reference_ids": [_text(item) for item in reference_ids],
        "schema_version": schema_version,
        "source_types": [item.value for item in source_types],
        "task_intent": _text(task_intent),
        "vision_refs": [
            {
                "image_type": item.image_type.value,
                "reference_id": _text(item.reference_id),
            }
            for item in vision_refs
        ],
    }


def snapshot_fingerprint(
    *,
    schema_version: str,
    context_id: str,
    task_intent: str,
    reference_ids: tuple[str, ...],
    source_types: tuple[SourceType, ...],
    datasheet_candidates: tuple[DatasheetContext, ...],
    file_summaries: tuple[FileContext, ...],
    vision_refs: tuple[VisionContext, ...],
) -> str:
    payload = canonical_snapshot_payload(
        schema_version=schema_version,
        context_id=context_id,
        task_intent=task_intent,
        reference_ids=reference_ids,
        source_types=source_types,
        datasheet_candidates=datasheet_candidates,
        file_summaries=file_summaries,
        vision_refs=vision_refs,
    )
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def build_reasoning_context_snapshot(
    request: EngineeringContextRequest,
    response: EngineeringContextResponse,
    *,
    expected_context_id: str,
) -> ReasoningContextSnapshot:
    try:
        isolated_request = EngineeringContextRequest.model_validate(
            copy.deepcopy(request.model_dump(mode="python"))
        )
        isolated_response = EngineeringContextResponse.model_validate(
            copy.deepcopy(response.model_dump(mode="python"))
        )
    except (AttributeError, TypeError, ValidationError):
        raise ReasoningRequestRejected() from None

    summary = isolated_response.context_summary
    if (
        summary.context_id != expected_context_id
        or summary.task_intent != isolated_request.task_intent
    ):
        raise ReasoningContextConflict()

    references = isolated_request.reference_ids
    reference_keys = {item.casefold() for item in references}
    datasheet_by_id = _unique_by_id(
        summary.datasheets,
        attribute="file_id",
        reference_keys=reference_keys,
    )
    file_by_id = _unique_by_id(
        summary.files,
        attribute="file_id",
        reference_keys=reference_keys,
    )
    vision_by_id = _unique_by_id(
        summary.vision,
        attribute="reference_id",
        reference_keys=reference_keys,
    )
    source_types: list[SourceType] = []
    for reference_id in references:
        key = reference_id.casefold()
        if key in vision_by_id:
            if key in datasheet_by_id or key in file_by_id:
                raise ReasoningContextConflict()
            source_types.append(SourceType.VISION)
        elif key in datasheet_by_id:
            if key not in file_by_id:
                raise ReasoningContextConflict()
            source_types.append(SourceType.DATASHEET)
        elif key in file_by_id:
            source_types.append(SourceType.FILE)
        else:
            raise ReasoningContextConflict()

    fingerprint = snapshot_fingerprint(
        schema_version="1.0",
        context_id=summary.context_id,
        task_intent=summary.task_intent,
        reference_ids=references,
        source_types=tuple(source_types),
        datasheet_candidates=summary.datasheets,
        file_summaries=summary.files,
        vision_refs=summary.vision,
    )
    return ReasoningContextSnapshot(
        snapshot_fingerprint=fingerprint,
        context_id=summary.context_id,
        task_intent=summary.task_intent,
        reference_ids=references,
        source_types=tuple(source_types),
        datasheet_candidates=summary.datasheets,
        file_summaries=summary.files,
        vision_refs=summary.vision,
    )


def _unique_by_id(
    items: tuple[Any, ...],
    *,
    attribute: str,
    reference_keys: set[str],
) -> dict[str, Any]:
    indexed: dict[str, Any] = {}
    for item in items:
        identifier = getattr(item, attribute)
        key = identifier.casefold()
        if key not in reference_keys or key in indexed:
            raise ReasoningContextConflict()
        indexed[key] = item
    return indexed
