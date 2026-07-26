from __future__ import annotations

import asyncio

import pytest

from embedded_copilot.datasheet_runtime import (
    DatasheetRequest,
    DatasheetRuntime,
    DatasheetRuntimeUnavailable,
    create_datasheet_runtime,
)
from embedded_copilot.file_runtime import FileExtractionPort


class _ExtractionPort:
    async def extract(self, request, extractor, *, result_type):
        raise AssertionError("foundation runtime must not read a file")


def test_factory_returns_isolated_runtime_with_safe_unavailable_port() -> None:
    source_port: FileExtractionPort = _ExtractionPort()
    runtime = create_datasheet_runtime(source_port)

    assert isinstance(runtime, DatasheetRuntime)
    with pytest.raises(DatasheetRuntimeUnavailable) as raised:
        asyncio.run(
            runtime.datasheet_port().analyze(
                DatasheetRequest(
                    session_id="session:1",
                    file_id="file:1",
                    instruction_summary="Extract candidates.",
                )
            )
        )

    assert str(raised.value) == "datasheet_unavailable"
    for forbidden in (
        "file_port",
        "extraction_port",
        "reader",
        "parser",
        "extractor",
        "settings",
        "configuration",
    ):
        assert not hasattr(runtime, forbidden)
        assert not hasattr(runtime.datasheet_port(), forbidden)


def test_runtime_requires_composition_factory() -> None:
    with pytest.raises(TypeError, match="composition factory"):
        DatasheetRuntime(_ExtractionPort())
