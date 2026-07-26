from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from embedded_copilot.context_runtime.contracts import (
    ComponentContextCandidate,
    ContextDocumentType,
    ContextImageType,
    ContextReference,
    ContextReferenceKind,
    DatasheetContext,
    EngineeringContextPort,
    EngineeringContextRequest,
    EngineeringContextResponse,
    EngineeringContextSummary,
    FileContext,
    InterfaceContextCandidate,
    SectionContextCandidate,
    VisionContext,
)


class _ContextPort:
    async def compose(
        self,
        request: EngineeringContextRequest,
    ) -> EngineeringContextResponse:
        return EngineeringContextResponse(
            context_summary=EngineeringContextSummary(
                context_id="context:0123456789abcdef01234567",
                task_intent=request.task_intent,
            )
        )


def test_context_contracts_are_frozen_and_forbid_extra_fields() -> None:
    request = EngineeringContextRequest(
        session_id="session:1",
        task_intent="Review referenced embedded context.",
        reference_ids=("file:1", "image:1"),
    )

    with pytest.raises(ValidationError, match="frozen"):
        request.task_intent = "Changed"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="extra"):
        EngineeringContextRequest.model_validate(
            {
                **request.model_dump(mode="python"),
                "path": "private.pdf",
            }
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("session_id", "../session"),
        ("task_intent", "Read C:\\private\\design.pdf"),
        ("task_intent", "api_key=PRIVATE_SECRET"),
        ("reference_ids", ("file:1", "FILE:1")),
    ),
)
def test_context_request_rejects_unsafe_or_duplicate_values(
    field: str,
    value: object,
) -> None:
    payload: dict[str, object] = {
        "session_id": "session:1",
        "task_intent": "Review referenced embedded context.",
        "reference_ids": ("file:1",),
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        EngineeringContextRequest.model_validate(payload)


def test_context_summary_preserves_source_scoped_candidate_semantics() -> None:
    summary = EngineeringContextSummary(
        context_id="context:0123456789abcdef01234567",
        task_intent="Review referenced embedded context.",
        datasheets=(
            DatasheetContext(
                file_id="file:datasheet-1",
                component_candidate=ComponentContextCandidate(
                    family="ESP32",
                    model="ESP32-S3",
                ),
                interfaces=(InterfaceContextCandidate(name="I2C"),),
                sections=(
                    SectionContextCandidate(name="Electrical Characteristics"),
                ),
            ),
        ),
        files=(
            FileContext(
                file_id="file:datasheet-1",
                document_type=ContextDocumentType.PDF,
                page_count=42,
            ),
        ),
        vision=(
            VisionContext(
                reference_id="image:1",
                image_type=ContextImageType.UNKNOWN,
            ),
        ),
    )

    assert summary.datasheets[0].component_candidate is not None
    assert summary.datasheets[0].component_candidate.semantics == "candidate"
    assert summary.datasheets[0].file_id == "file:datasheet-1"
    assert summary.files[0].page_count == 42
    assert summary.vision[0].image_type == ContextImageType.UNKNOWN


def test_reference_descriptor_requires_kind_specific_metadata() -> None:
    file_reference = ContextReference(
        reference_id="file:1",
        kind=ContextReferenceKind.FILE,
        document_type=ContextDocumentType.SOURCE_CODE,
    )

    assert file_reference.image_type is None
    with pytest.raises(ValidationError):
        ContextReference(
            reference_id="image:1",
            kind=ContextReferenceKind.VISION,
        )


def test_context_port_exposes_only_compose_contract() -> None:
    request = EngineeringContextRequest(
        session_id="session:1",
        task_intent="Review referenced embedded context.",
        reference_ids=(),
    )
    response = asyncio.run(_ContextPort().compose(request))

    assert isinstance(_ContextPort(), EngineeringContextPort)
    assert response.output_type == "context_summary"
    assert response.review_required is True
    assert {
        name
        for name, value in EngineeringContextPort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"compose"}
