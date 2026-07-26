from __future__ import annotations

import asyncio

import pytest

from embedded_copilot.context_runtime.aggregation import ContextComposer
from embedded_copilot.context_runtime.contracts import (
    ComponentContextCandidate,
    ContextDocumentType,
    ContextImageType,
    ContextReference,
    ContextReferenceKind,
    DatasheetContext,
    EngineeringContextRequest,
    FileContext,
    InterfaceContextCandidate,
    VisionContext,
)
from embedded_copilot.context_runtime.exceptions import (
    EngineeringContextConflict,
    EngineeringContextReferenceNotFound,
    EngineeringContextUnavailable,
)


class _Resolver:
    def __init__(self, references: tuple[ContextReference, ...]) -> None:
        self.references = references
        self.requests: list[EngineeringContextRequest] = []

    def resolve(
        self,
        request: EngineeringContextRequest,
    ) -> tuple[ContextReference, ...]:
        self.requests.append(request)
        return self.references


class _FileSource:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.outcome: Exception | None = None

    async def summarize(
        self,
        request: EngineeringContextRequest,
        reference: ContextReference,
    ) -> FileContext:
        self.calls.append(reference.reference_id)
        if self.outcome is not None:
            raise self.outcome
        if reference.document_type in {
            ContextDocumentType.PDF,
            ContextDocumentType.DATASHEET,
        }:
            return FileContext(
                file_id=reference.reference_id,
                document_type=reference.document_type,
                page_count=42,
            )
        return FileContext(
            file_id=reference.reference_id,
            document_type=reference.document_type,
            line_count=120,
            character_count=4096,
        )


class _DatasheetSource:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def summarize(
        self,
        request: EngineeringContextRequest,
        reference: ContextReference,
    ) -> DatasheetContext:
        self.calls.append(reference.reference_id)
        model = "ESP32-S3" if reference.reference_id.endswith("1") else "ESP32-C3"
        return DatasheetContext(
            file_id=reference.reference_id,
            component_candidate=ComponentContextCandidate(
                family="ESP32",
                model=model,
            ),
            interfaces=(InterfaceContextCandidate(name="SPI"),),
        )


class _VisionSource:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def summarize(
        self,
        request: EngineeringContextRequest,
        reference: ContextReference,
    ) -> VisionContext:
        self.calls.append(reference.reference_id)
        assert reference.image_type is not None
        return VisionContext(
            reference_id=reference.reference_id,
            image_type=reference.image_type,
        )


def _request(*reference_ids: str) -> EngineeringContextRequest:
    return EngineeringContextRequest(
        session_id="session:1",
        task_intent="Review referenced embedded context.",
        reference_ids=reference_ids,
    )


def _reference(
    reference_id: str,
    kind: ContextReferenceKind,
) -> ContextReference:
    if kind is ContextReferenceKind.VISION:
        return ContextReference(
            reference_id=reference_id,
            kind=kind,
            image_type=ContextImageType.UNKNOWN,
        )
    return ContextReference(
        reference_id=reference_id,
        kind=kind,
        document_type=(
            ContextDocumentType.PDF
            if kind is ContextReferenceKind.DATASHEET
            else ContextDocumentType.SOURCE_CODE
        ),
    )


def test_composer_uses_deterministic_branch_and_reference_order() -> None:
    references = (
        _reference("file:source-1", ContextReferenceKind.FILE),
        _reference("image:1", ContextReferenceKind.VISION),
        _reference("file:datasheet-1", ContextReferenceKind.DATASHEET),
        _reference("file:datasheet-2", ContextReferenceKind.DATASHEET),
    )
    resolver = _Resolver(tuple(reversed(references)))
    files = _FileSource()
    datasheets = _DatasheetSource()
    vision = _VisionSource()
    composer = ContextComposer(
        reference_resolver=resolver,
        file_source=files,
        datasheet_source=datasheets,
        vision_source=vision,
    )

    response = asyncio.run(
        composer.compose(_request(*(item.reference_id for item in references)))
    )

    assert response.context_summary.context_id == "context:179b2d7209ace7a5e1784186"
    assert datasheets.calls == ["file:datasheet-1", "file:datasheet-2"]
    assert files.calls == [
        "file:source-1",
        "file:datasheet-1",
        "file:datasheet-2",
    ]
    assert vision.calls == ["image:1"]
    assert tuple(item.file_id for item in response.context_summary.datasheets) == (
        "file:datasheet-1",
        "file:datasheet-2",
    )
    assert tuple(item.file_id for item in response.context_summary.files) == (
        "file:source-1",
        "file:datasheet-1",
        "file:datasheet-2",
    )
    assert response.context_summary.vision[0].reference_id == "image:1"


def test_composer_context_id_is_deterministic_without_state() -> None:
    request = _request()
    first = ContextComposer(
        reference_resolver=_Resolver(()),
        file_source=_FileSource(),
        datasheet_source=_DatasheetSource(),
        vision_source=_VisionSource(),
    )
    second = ContextComposer(
        reference_resolver=_Resolver(()),
        file_source=_FileSource(),
        datasheet_source=_DatasheetSource(),
        vision_source=_VisionSource(),
    )

    first_response = asyncio.run(first.compose(request))
    second_response = asyncio.run(second.compose(request))

    assert first_response == second_response
    assert first_response.context_summary.datasheets == ()
    assert first_response.context_summary.files == ()
    assert first_response.context_summary.vision == ()


@pytest.mark.parametrize(
    "resolved",
    (
        (),
        (_reference("file:other", ContextReferenceKind.FILE),),
        (
            _reference("file:source-1", ContextReferenceKind.FILE),
            _reference("FILE:SOURCE-1", ContextReferenceKind.FILE),
        ),
    ),
)
def test_composer_rejects_incomplete_or_conflicting_resolution(
    resolved: tuple[ContextReference, ...],
) -> None:
    composer = ContextComposer(
        reference_resolver=_Resolver(resolved),
        file_source=_FileSource(),
        datasheet_source=_DatasheetSource(),
        vision_source=_VisionSource(),
    )

    with pytest.raises(EngineeringContextConflict):
        asyncio.run(composer.compose(_request("file:source-1")))


def test_composer_fails_closed_without_partial_result() -> None:
    files = _FileSource()
    files.outcome = RuntimeError("PRIVATE_SOURCE_FAILURE")
    composer = ContextComposer(
        reference_resolver=_Resolver(
            (_reference("file:source-1", ContextReferenceKind.FILE),)
        ),
        file_source=files,
        datasheet_source=_DatasheetSource(),
        vision_source=_VisionSource(),
    )

    with pytest.raises(EngineeringContextUnavailable) as captured:
        asyncio.run(composer.compose(_request("file:source-1")))

    assert "PRIVATE_SOURCE_FAILURE" not in str(captured.value)


def test_composer_preserves_safe_context_errors() -> None:
    files = _FileSource()
    files.outcome = EngineeringContextReferenceNotFound()
    composer = ContextComposer(
        reference_resolver=_Resolver(
            (_reference("file:source-1", ContextReferenceKind.FILE),)
        ),
        file_source=files,
        datasheet_source=_DatasheetSource(),
        vision_source=_VisionSource(),
    )

    with pytest.raises(EngineeringContextReferenceNotFound):
        asyncio.run(composer.compose(_request("file:source-1")))
