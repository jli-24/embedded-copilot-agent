from __future__ import annotations

from embedded_copilot.context_runtime.aggregation import ContextComposer
from embedded_copilot.context_runtime.contracts import (
    ContextReferenceResolver,
    DatasheetContextSource,
    FileContextSource,
    VisionContextSource,
)
from embedded_copilot.context_runtime.exceptions import (
    EngineeringContextUnavailable,
)
from embedded_copilot.context_runtime.facade import EngineeringContextRuntime


def create_engineering_context_runtime(
    *,
    file_port: FileContextSource,
    datasheet_port: DatasheetContextSource,
    vision_port: VisionContextSource,
    reference_resolver: ContextReferenceResolver,
) -> EngineeringContextRuntime:
    if (
        not isinstance(file_port, FileContextSource)
        or not isinstance(datasheet_port, DatasheetContextSource)
        or not isinstance(vision_port, VisionContextSource)
        or not isinstance(reference_resolver, ContextReferenceResolver)
    ):
        raise EngineeringContextUnavailable()
    return EngineeringContextRuntime._compose(
        ContextComposer(
            reference_resolver=reference_resolver,
            file_source=file_port,
            datasheet_source=datasheet_port,
            vision_source=vision_port,
        )
    )
