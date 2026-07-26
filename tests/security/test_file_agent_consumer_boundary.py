from __future__ import annotations

import asyncio

from embedded_copilot.file_runtime import (
    FileIntelligencePort,
    FileIntelligenceResponse,
    FileReferenceRequest,
    FileType,
)


class _ReadOnlyPort:
    async def analyze(
        self,
        request: FileReferenceRequest,
    ) -> FileIntelligenceResponse:
        return FileIntelligenceResponse(
            summary="SOURCE_CODE file structure: 4 lines, 80 characters."
        )


class FutureCodingAgent:
    __slots__ = ("_file_port",)

    def __init__(self, file_port: FileIntelligencePort) -> None:
        self._file_port = file_port

    async def analyze(self) -> FileIntelligenceResponse:
        return await self._file_port.analyze(
            FileReferenceRequest(
                session_id="session:1",
                file_id="file:1",
                file_type=FileType.UNKNOWN,
                instruction_summary="Inspect structure only.",
            )
        )


def test_future_agent_consumer_has_analysis_only_capability() -> None:
    consumer = FutureCodingAgent(_ReadOnlyPort())

    response = asyncio.run(consumer.analyze())

    assert response.summary == ("SOURCE_CODE file structure: 4 lines, 80 characters.")
    for forbidden in (
        "write",
        "patch",
        "execute",
        "path",
        "reader",
        "catalog",
        "filesystem",
        "configuration",
    ):
        assert not hasattr(consumer, forbidden)
        assert not hasattr(consumer._file_port, forbidden)


def test_file_port_has_no_write_or_execution_contract() -> None:
    for forbidden in (
        "write",
        "edit_file",
        "patch_file",
        "save_file",
        "generate_code",
        "execute",
        "change_configuration",
    ):
        assert not hasattr(FileIntelligencePort, forbidden)
