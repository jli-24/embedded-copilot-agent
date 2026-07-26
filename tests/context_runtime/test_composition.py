from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from embedded_copilot.api.context_adapters import (
    CopilotContextReferenceResolver,
    CopilotDatasheetContextSource,
    CopilotFileContextSource,
    CopilotVisionContextSource,
)
from embedded_copilot.context_runtime import (
    EngineeringContextRuntime,
    create_engineering_context_runtime,
)
from embedded_copilot.context_runtime.contracts import (
    ContextReferenceKind,
    EngineeringContextRequest,
)
from embedded_copilot.context_runtime.exceptions import (
    EngineeringContextReferenceNotFound,
    EngineeringContextRejected,
)
from embedded_copilot.datasheet_runtime import (
    DatasheetRequest,
    DatasheetResponse,
    DatasheetSummary,
)
from embedded_copilot.datasheet_runtime.contracts.models import (
    ComponentCandidate,
    InterfaceCandidate,
    SectionCandidate,
)
from embedded_copilot.file_runtime import (
    FileIntelligenceResponse,
    FileReferenceRequest,
)
from embedded_copilot.multimodal.context import (
    AttachmentBinding,
    ProcessLocalAttachmentBindingRepository,
)
from embedded_copilot.multimodal.models import (
    MultimodalInput,
    MultimodalInputType,
)
from embedded_copilot.vision_runtime import VisionRequest, VisionResponse

CREATED = datetime(2026, 7, 27, 8, 0, tzinfo=timezone.utc)


class _FilePort:
    def __init__(self) -> None:
        self.calls: list[FileReferenceRequest] = []

    async def analyze(
        self,
        request: FileReferenceRequest,
    ) -> FileIntelligenceResponse:
        self.calls.append(request)
        summary = (
            "PDF file structure: 64 pages."
            if request.file_id.startswith("file:datasheet")
            else "SOURCE_CODE file structure: 120 lines, 4096 characters."
        )
        return FileIntelligenceResponse(summary=summary)


class _DatasheetPort:
    def __init__(self) -> None:
        self.calls: list[DatasheetRequest] = []

    async def analyze(self, request: DatasheetRequest) -> DatasheetResponse:
        self.calls.append(request)
        return DatasheetResponse(
            summary=DatasheetSummary(
                file_id=request.file_id,
                component_candidate=ComponentCandidate(
                    family="ESP32",
                    model="ESP32-S3",
                ),
                interface_candidates=(InterfaceCandidate(name="I2C"),),
                section_candidates=(
                    SectionCandidate(name="Electrical Characteristics"),
                ),
            )
        )


class _VisionPort:
    def __init__(self) -> None:
        self.calls: list[VisionRequest] = []

    async def analyze(self, request: VisionRequest) -> VisionResponse:
        self.calls.append(request)
        raise AssertionError("context composition must not trigger vision inference")


def _binding(
    reference_id: str,
    input_type: MultimodalInputType,
    basename: str,
) -> AttachmentBinding:
    return AttachmentBinding(
        session_id="session:1",
        input=MultimodalInput(
            type=input_type,
            reference_id=reference_id,
            summary="Registered reference metadata.",
        ),
        basename=basename,
        size_bytes=1024,
        created_at=CREATED,
    )


def _runtime() -> tuple[
    EngineeringContextRuntime,
    _FilePort,
    _DatasheetPort,
    _VisionPort,
]:
    repository = ProcessLocalAttachmentBindingRepository()
    repository.bind(_binding("file:source-1", MultimodalInputType.FILE, "main.c"))
    repository.bind(_binding("file:datasheet-1", MultimodalInputType.FILE, "mcu.pdf"))
    repository.bind(_binding("image:1", MultimodalInputType.IMAGE, "schematic.png"))
    file_port = _FilePort()
    datasheet_port = _DatasheetPort()
    vision_port = _VisionPort()
    runtime = create_engineering_context_runtime(
        file_port=CopilotFileContextSource(file_port),
        datasheet_port=CopilotDatasheetContextSource(datasheet_port),
        vision_port=CopilotVisionContextSource(vision_port),
        reference_resolver=CopilotContextReferenceResolver(repository),
    )
    return runtime, file_port, datasheet_port, vision_port


def test_factory_composes_safe_upstream_adapters() -> None:
    runtime, file_port, datasheet_port, vision_port = _runtime()
    request = EngineeringContextRequest(
        session_id="session:1",
        task_intent="Review referenced embedded context.",
        reference_ids=("file:source-1", "file:datasheet-1", "image:1"),
    )

    response = asyncio.run(runtime.context_port().compose(request))

    summary = response.context_summary
    assert tuple(item.file_id for item in summary.files) == (
        "file:source-1",
        "file:datasheet-1",
    )
    assert summary.files[0].line_count == 120
    assert summary.files[1].page_count == 64
    assert summary.datasheets[0].component_candidate is not None
    assert summary.datasheets[0].component_candidate.model == "ESP32-S3"
    assert summary.vision[0].reference_id == "image:1"
    assert len(file_port.calls) == 2
    assert len(datasheet_port.calls) == 1
    assert vision_port.calls == []


def test_reference_resolver_classifies_only_safe_metadata() -> None:
    repository = ProcessLocalAttachmentBindingRepository()
    repository.bind(_binding("file:1", MultimodalInputType.FILE, "guide.pdf"))
    repository.bind(_binding("image:1", MultimodalInputType.IMAGE, "board.png"))
    resolver = CopilotContextReferenceResolver(repository)

    references = resolver.resolve(
        EngineeringContextRequest(
            session_id="session:1",
            task_intent="Review referenced embedded context.",
            reference_ids=("file:1", "image:1"),
        )
    )

    assert tuple(item.kind for item in references) == (
        ContextReferenceKind.DATASHEET,
        ContextReferenceKind.VISION,
    )
    assert "basename" not in references[0].model_dump()
    assert "path" not in references[0].model_dump()


def test_reference_resolver_maps_missing_and_unsupported_references() -> None:
    repository = ProcessLocalAttachmentBindingRepository()
    resolver = CopilotContextReferenceResolver(repository)
    request = EngineeringContextRequest(
        session_id="session:1",
        task_intent="Review referenced embedded context.",
        reference_ids=("file:missing",),
    )

    with pytest.raises(EngineeringContextReferenceNotFound):
        resolver.resolve(request)

    repository.bind(_binding("file:missing", MultimodalInputType.FILE, "blob.bin"))
    with pytest.raises(EngineeringContextRejected):
        resolver.resolve(request)
