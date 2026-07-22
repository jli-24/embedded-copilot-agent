from __future__ import annotations

import asyncio

from embedded_copilot.schemas.result import ErrorCode, ToolStatus
from embedded_copilot.services.llm import OfflineLLMService
from embedded_copilot.tools.code_tool import (
    CodeAnalysisInput,
    CodeAnalysisTool,
    CodeOperation,
)


class BrokenCodeService:
    def generate_firmware(self, **kwargs: object) -> object:
        return {"unexpected": "payload"}


def test_code_tool_generates_reviewable_freertos_led_example() -> None:
    tool = CodeAnalysisTool(llm=OfflineLLMService(), timeout_seconds=1.0)
    payload = CodeAnalysisInput(
        operation=CodeOperation.GENERATE,
        request="生成 ESP32 FreeRTOS LED 任务",
        language="C",
        platform="ESP-IDF",
    )

    result = asyncio.run(tool.invoke(payload))

    assert result.status is ToolStatus.SUCCESS
    assert result.data is not None
    assert "CONFIG_LED_GPIO" in result.data.code
    assert any("hardware" in item.lower() for item in result.data.limitations)


def test_code_tool_maps_malformed_model_output() -> None:
    tool = CodeAnalysisTool(llm=BrokenCodeService(), timeout_seconds=1.0)

    result = asyncio.run(
        tool.invoke(
            CodeAnalysisInput(
                operation=CodeOperation.EXPLAIN,
                request="Explain this code",
                code="void app_main(void) {}",
            )
        )
    )

    assert result.status is ToolStatus.ERROR
    assert result.error is not None
    assert result.error.code is ErrorCode.MODEL_ERROR
