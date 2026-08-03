"""ReasoningPort adapter for constrained ESP-IDF proposal generation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from embedded_copilot.conversation.models import ReasoningOutput
from embedded_copilot.conversation.reasoning import ReasoningPort
from embedded_copilot.firmware_agent.models import FirmwareSourceFile

_INSTRUCTION = (
    "Return one JSON object with exactly files. files must contain CMakeLists.txt "
    "and main/main.c and may only use the approved ESP-IDF logical paths. Each "
    "item must contain logical_path, purpose, and content. This is an unverified "
    "proposal; do not claim build or hardware validation."
)


class _RawFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    logical_path: str
    purpose: str
    content: str


class _RawProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    files: tuple[_RawFile, ...]

    @field_validator("files", mode="before")
    @classmethod
    def normalize_json_files(cls, value: object) -> object:
        if type(value) is list:
            return tuple(value)
        return value


class FirmwareReasoningGenerator:
    __slots__ = ("_reasoning",)

    def __init__(self, reasoning_port: ReasoningPort) -> None:
        if not isinstance(reasoning_port, ReasoningPort):
            raise TypeError("reasoning_port is invalid")
        self._reasoning = reasoning_port

    async def generate(self, request) -> tuple[FirmwareSourceFile, ...]:
        output = await self._reasoning.reason(
            user_message_summary=request.context.project_summary,
            context_summaries=(
                request.context.current_stage,
                *(item.summary for item in request.knowledge),
                _INSTRUCTION,
            ),
            task_intent="FIRMWARE_GENERATION",
        )
        if type(output) is not ReasoningOutput:
            raise ValueError("reasoning output is invalid")
        checked = ReasoningOutput.model_validate(output.model_copy(deep=True))
        raw = _RawProposal.model_validate_json(checked.response.text)
        files = []
        from embedded_copilot.firmware_agent.models import (
            firmware_source_file_fingerprint,
        )

        for item in raw.files:
            values = {
                "logical_path": item.logical_path,
                "purpose": item.purpose,
                "content": item.content,
            }
            files.append(
                FirmwareSourceFile(
                    **values,
                    fingerprint=firmware_source_file_fingerprint(**values),
                )
            )
        return tuple(sorted(files, key=lambda item: item.logical_path))
