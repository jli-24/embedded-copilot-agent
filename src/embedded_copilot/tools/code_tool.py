from __future__ import annotations

import asyncio
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from embedded_copilot.schemas.result import (
    ContractModel,
    ErrorCode,
    ErrorDetail,
    FirmwareResult,
    ToolResult,
    ToolStatus,
)
from embedded_copilot.services.llm import LLMService


class CodeOperation(StrEnum):
    EXPLAIN = "explain"
    GENERATE = "generate"
    ARCHITECTURE = "architecture"


class CodeAnalysisInput(ContractModel):
    operation: CodeOperation
    request: str = Field(min_length=1, max_length=20_000)
    code: str | None = Field(default=None, max_length=100_000)
    language: str = "C"
    platform: str = "generic embedded"

    @field_validator("request", mode="before")
    @classmethod
    def strip_request(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_code_for_explanation(self) -> "CodeAnalysisInput":
        if self.operation is CodeOperation.EXPLAIN and not (self.code or "").strip():
            raise ValueError("code is required for explain operations")
        return self


class CodeAnalysisTool:
    def __init__(self, *, llm: LLMService, timeout_seconds: float) -> None:
        self._llm = llm
        self._timeout_seconds = timeout_seconds

    async def invoke(
        self,
        payload: CodeAnalysisInput,
    ) -> ToolResult[FirmwareResult]:
        try:
            raw_result = await asyncio.wait_for(
                asyncio.to_thread(
                    self._llm.generate_firmware,
                    operation=payload.operation.value,
                    request=payload.request,
                    code=payload.code,
                    language=payload.language,
                    platform=payload.platform,
                ),
                timeout=self._timeout_seconds,
            )
            result = FirmwareResult.model_validate(raw_result)
        except TimeoutError:
            return ToolResult[FirmwareResult](
                status=ToolStatus.ERROR,
                error=ErrorDetail(
                    code=ErrorCode.TIMEOUT,
                    message="Code analysis timed out.",
                    retryable=True,
                ),
            )
        except Exception:
            return ToolResult[FirmwareResult](
                status=ToolStatus.ERROR,
                error=ErrorDetail(
                    code=ErrorCode.MODEL_ERROR,
                    message="Code analysis returned an invalid result.",
                    retryable=False,
                ),
            )
        return ToolResult[FirmwareResult](status=ToolStatus.SUCCESS, data=result)
