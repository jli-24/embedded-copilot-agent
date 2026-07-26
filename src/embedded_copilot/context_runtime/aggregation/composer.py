from __future__ import annotations

import asyncio
import copy

from embedded_copilot.context_runtime.aggregation.validators import (
    canonical_context_id,
    order_resolved_references,
)
from embedded_copilot.context_runtime.contracts import (
    ContextReference,
    ContextReferenceKind,
    ContextReferenceResolver,
    DatasheetContext,
    DatasheetContextSource,
    EngineeringContextRequest,
    EngineeringContextResponse,
    EngineeringContextSummary,
    FileContext,
    FileContextSource,
    VisionContext,
    VisionContextSource,
)
from embedded_copilot.context_runtime.exceptions import (
    EngineeringContextConflict,
    EngineeringContextError,
    EngineeringContextUnavailable,
)


class ContextComposer:
    __slots__ = (
        "_datasheet_source",
        "_file_source",
        "_reference_resolver",
        "_vision_source",
    )

    def __init__(
        self,
        *,
        reference_resolver: ContextReferenceResolver,
        file_source: FileContextSource,
        datasheet_source: DatasheetContextSource,
        vision_source: VisionContextSource,
    ) -> None:
        self._reference_resolver = reference_resolver
        self._file_source = file_source
        self._datasheet_source = datasheet_source
        self._vision_source = vision_source

    async def compose(
        self,
        request: EngineeringContextRequest,
    ) -> EngineeringContextResponse:
        isolated_request = EngineeringContextRequest.model_validate(
            copy.deepcopy(request.model_dump(mode="python"))
        )
        try:
            raw_references = self._reference_resolver.resolve(isolated_request)
            references = tuple(
                ContextReference.model_validate(
                    copy.deepcopy(reference.model_dump(mode="python"))
                )
                for reference in raw_references
            )
            ordered = order_resolved_references(isolated_request, references)
            datasheets = await self._compose_datasheets(isolated_request, ordered)
            files = await self._compose_files(isolated_request, ordered)
            vision = await self._compose_vision(isolated_request, ordered)
            summary = EngineeringContextSummary(
                context_id=canonical_context_id(isolated_request),
                task_intent=isolated_request.task_intent,
                datasheets=datasheets,
                files=files,
                vision=vision,
            )
            return EngineeringContextResponse(context_summary=summary)
        except asyncio.CancelledError:
            raise
        except EngineeringContextError:
            raise
        except Exception:
            raise EngineeringContextUnavailable() from None

    async def _compose_datasheets(
        self,
        request: EngineeringContextRequest,
        references: tuple[ContextReference, ...],
    ) -> tuple[DatasheetContext, ...]:
        results: list[DatasheetContext] = []
        for reference in references:
            if reference.kind is not ContextReferenceKind.DATASHEET:
                continue
            result = await self._datasheet_source.summarize(request, reference)
            isolated = DatasheetContext.model_validate(
                copy.deepcopy(result.model_dump(mode="python"))
            )
            if isolated.file_id.casefold() != reference.reference_id.casefold():
                raise EngineeringContextConflict()
            results.append(isolated)
        return tuple(results)

    async def _compose_files(
        self,
        request: EngineeringContextRequest,
        references: tuple[ContextReference, ...],
    ) -> tuple[FileContext, ...]:
        results: list[FileContext] = []
        for reference in references:
            if reference.kind is ContextReferenceKind.VISION:
                continue
            result = await self._file_source.summarize(request, reference)
            isolated = FileContext.model_validate(
                copy.deepcopy(result.model_dump(mode="python"))
            )
            if (
                isolated.file_id.casefold() != reference.reference_id.casefold()
                or isolated.document_type is not reference.document_type
            ):
                raise EngineeringContextConflict()
            results.append(isolated)
        return tuple(results)

    async def _compose_vision(
        self,
        request: EngineeringContextRequest,
        references: tuple[ContextReference, ...],
    ) -> tuple[VisionContext, ...]:
        results: list[VisionContext] = []
        for reference in references:
            if reference.kind is not ContextReferenceKind.VISION:
                continue
            result = await self._vision_source.summarize(request, reference)
            isolated = VisionContext.model_validate(
                copy.deepcopy(result.model_dump(mode="python"))
            )
            if (
                isolated.reference_id.casefold() != reference.reference_id.casefold()
                or isolated.image_type is not reference.image_type
            ):
                raise EngineeringContextConflict()
            results.append(isolated)
        return tuple(results)
