from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from embedded_copilot.schemas.result import ToolStatus
from embedded_copilot.services.llm import OfflineLLMService
from embedded_copilot.tools.debug_tool import DebugLogInput, DebugLogTool


def test_debug_tool_separates_evidence_from_inference() -> None:
    log = (
        "Guru Meditation Error: Core 1 panic'ed (LoadProhibited).\n"
        "Backtrace: 0x40081234:0x3ffb1230 0x40084567:0x3ffb1250"
    )
    tool = DebugLogTool(llm=OfflineLLMService(), timeout_seconds=1.0)

    result = asyncio.run(tool.invoke(DebugLogInput(log=log, platform="ESP32")))

    assert result.status is ToolStatus.SUCCESS
    assert result.data is not None
    assert result.data.problem_type == "ESP32 Guru Meditation"
    assert any("Guru Meditation" in item for item in result.data.evidence)
    assert any("memory" in item.lower() for item in result.data.root_cause)
    assert result.data.confidence == "medium"
    assert result.data.next_steps


def test_debug_log_input_rejects_blank_log() -> None:
    with pytest.raises(ValidationError):
        DebugLogInput(log="  ")
