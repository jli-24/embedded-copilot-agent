from __future__ import annotations

import asyncio

from pydantic import Field, field_validator

from embedded_copilot.schemas.result import (
    ContractModel,
    DebugResult,
    ErrorCode,
    ErrorDetail,
    ToolResult,
    ToolStatus,
)
from embedded_copilot.services.llm import LLMService


class DebugLogInput(ContractModel):
    log: str = Field(min_length=1, max_length=100_000)
    platform: str | None = None

    @field_validator("log", mode="before")
    @classmethod
    def strip_log(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


def _extract_evidence(log: str) -> list[str]:
    markers = (
        "guru meditation",
        "backtrace",
        "hardfault",
        "hard fault",
        "error:",
        "warning:",
    )
    return [
        line.strip()
        for line in log.splitlines()
        if line.strip() and any(marker in line.lower() for marker in markers)
    ]


class DebugLogTool:
    def __init__(self, *, llm: LLMService, timeout_seconds: float) -> None:
        self._llm = llm
        self._timeout_seconds = timeout_seconds

    async def invoke(self, payload: DebugLogInput) -> ToolResult[DebugResult]:
        evidence = _extract_evidence(payload.log)
        try:
            raw_result = await asyncio.wait_for(
                asyncio.to_thread(
                    self._llm.analyze_debug,
                    log=payload.log,
                    platform=payload.platform,
                    evidence=evidence,
                ),
                timeout=self._timeout_seconds,
            )
            result = DebugResult.model_validate(raw_result)
        except TimeoutError:
            return ToolResult[DebugResult](
                status=ToolStatus.ERROR,
                error=ErrorDetail(
                    code=ErrorCode.TIMEOUT,
                    message="Debug log analysis timed out.",
                    retryable=True,
                ),
            )
        except Exception:
            return ToolResult[DebugResult](
                status=ToolStatus.ERROR,
                error=ErrorDetail(
                    code=ErrorCode.MODEL_ERROR,
                    message="Debug log analysis returned an invalid result.",
                    retryable=False,
                ),
            )
        return ToolResult[DebugResult](status=ToolStatus.SUCCESS, data=result)
