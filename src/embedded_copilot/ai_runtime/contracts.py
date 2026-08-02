"""AI Runtime Ports."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.ai_runtime.models import (
    EngineeringChatRequest,
    EngineeringModelOutput,
    EngineeringModelRequest,
    EngineeringResponse,
    KnowledgeEvidenceProjection,
)


@runtime_checkable
class EngineeringChatPort(Protocol):
    async def chat(self, request: EngineeringChatRequest) -> EngineeringResponse: ...


@runtime_checkable
class EngineeringChatModelPort(Protocol):
    async def generate(
        self,
        request: EngineeringModelRequest,
    ) -> EngineeringModelOutput: ...


@runtime_checkable
class EngineeringKnowledgePort(Protocol):
    def retrieve(
        self,
        *,
        request_id: str,
        query_summary: str,
    ) -> tuple[KnowledgeEvidenceProjection, ...]: ...

