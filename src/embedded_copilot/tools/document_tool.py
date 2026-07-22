from __future__ import annotations

import asyncio
from typing import Protocol

from pydantic import Field, field_validator

from embedded_copilot.rag.retriever import RetrievedChunk
from embedded_copilot.schemas.result import (
    ContractModel,
    ErrorCode,
    ErrorDetail,
    SourceCitation,
    ToolResult,
    ToolStatus,
)
from embedded_copilot.services.llm import LLMService


class Retriever(Protocol):
    def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        score_threshold: float,
    ) -> list[RetrievedChunk]: ...


class DocumentSearchInput(ContractModel):
    query: str = Field(min_length=1, max_length=20_000)
    top_k: int = Field(default=4, ge=1, le=20)
    score_threshold: float = Field(default=0.15, ge=0.0, le=1.0)

    @field_validator("query", mode="before")
    @classmethod
    def strip_query(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class RetrievedItem(ContractModel):
    chunk_id: str
    text: str
    citation: SourceCitation
    chapter: str | None = None


class DocumentSearchOutput(ContractModel):
    answer: str
    items: list[RetrievedItem] = Field(default_factory=list)
    insufficient_context: bool = False


class DocumentSearchTool:
    def __init__(
        self,
        *,
        retriever: Retriever,
        llm: LLMService,
        timeout_seconds: float,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._timeout_seconds = timeout_seconds

    async def invoke(
        self,
        payload: DocumentSearchInput,
    ) -> ToolResult[DocumentSearchOutput]:
        try:
            chunks = await asyncio.wait_for(
                asyncio.to_thread(
                    self._retriever.retrieve,
                    payload.query,
                    top_k=payload.top_k,
                    score_threshold=payload.score_threshold,
                ),
                timeout=self._timeout_seconds,
            )
        except TimeoutError:
            return ToolResult[DocumentSearchOutput](
                status=ToolStatus.ERROR,
                error=ErrorDetail(
                    code=ErrorCode.TIMEOUT,
                    message="Document retrieval timed out.",
                    retryable=True,
                ),
            )
        except Exception:
            return ToolResult[DocumentSearchOutput](
                status=ToolStatus.ERROR,
                error=ErrorDetail(
                    code=ErrorCode.RETRIEVAL_ERROR,
                    message="Document retrieval failed.",
                    retryable=False,
                ),
            )

        if not chunks:
            return ToolResult[DocumentSearchOutput](
                status=ToolStatus.SUCCESS,
                data=DocumentSearchOutput(
                    answer="没有在当前 Embedded Knowledge Base 中找到相关内容。",
                    insufficient_context=True,
                ),
            )
        try:
            answer = await asyncio.wait_for(
                asyncio.to_thread(
                    self._llm.answer_knowledge,
                    query=payload.query,
                    contexts=[chunk.text for chunk in chunks],
                ),
                timeout=self._timeout_seconds,
            )
        except TimeoutError:
            return ToolResult[DocumentSearchOutput](
                status=ToolStatus.ERROR,
                error=ErrorDetail(
                    code=ErrorCode.TIMEOUT,
                    message="Knowledge synthesis timed out.",
                    retryable=True,
                ),
            )
        except Exception:
            return ToolResult[DocumentSearchOutput](
                status=ToolStatus.ERROR,
                error=ErrorDetail(
                    code=ErrorCode.MODEL_ERROR,
                    message="Knowledge synthesis failed.",
                    retryable=False,
                ),
            )
        return ToolResult[DocumentSearchOutput](
            status=ToolStatus.SUCCESS,
            data=DocumentSearchOutput(
                answer=answer,
                items=[
                    RetrievedItem(
                        chunk_id=chunk.chunk_id,
                        text=chunk.text,
                        citation=chunk.citation,
                        chapter=chunk.metadata.chapter,
                    )
                    for chunk in chunks
                ],
            ),
        )
