from __future__ import annotations

import asyncio
import logging

import pytest

from embedded_copilot.schemas.state import AgentState
from embedded_copilot.services.copilot import CopilotService


class FailingGraph:
    async def ainvoke(self, state: AgentState) -> AgentState:
        raise RuntimeError("private workflow detail")


def test_workflow_exception_emits_safe_terminal_events(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    service = CopilotService(FailingGraph())

    with pytest.raises(RuntimeError, match="private workflow detail"):
        asyncio.run(service.chat("ESP32 SPI", trace_id="trace-failure"))

    records = [
        record
        for record in caplog.records
        if getattr(record, "trace_id", None) == "trace-failure"
    ]
    assert [getattr(record, "event_name", None) for record in records] == [
        "workflow_start",
        "error_occurred",
        "workflow_completed",
    ]
    assert getattr(records[-1], "outcome", None) == "failed"
    assert "private workflow detail" not in caplog.text
    assert all(record.exc_info is None for record in records)
