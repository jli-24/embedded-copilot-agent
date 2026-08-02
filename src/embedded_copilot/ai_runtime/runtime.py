"""Stateless structured Engineering Chat orchestration."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.ai_runtime.contracts import (
    EngineeringChatModelPort,
    EngineeringChatPort,
    EngineeringKnowledgePort,
)
from embedded_copilot.ai_runtime.exceptions import AIModelUnavailable, AIRequestRejected
from embedded_copilot.ai_runtime.models import (
    EngineeringChatRequest,
    EngineeringModelOutput,
    EngineeringModelRequest,
    EngineeringResponse,
    KnowledgeEvidenceProjection,
    engineering_response_fingerprint,
)
from embedded_copilot.engineering_events import (
    EngineeringEvent,
    EngineeringEventType,
    engineering_event_fingerprint,
)


class _EngineeringChatService:
    __slots__ = ("_knowledge", "_max_attempts", "_model")

    def __init__(
        self,
        *,
        model_port: EngineeringChatModelPort,
        knowledge_port: EngineeringKnowledgePort | None,
        max_attempts: int,
    ) -> None:
        self._model = model_port
        self._knowledge = knowledge_port
        self._max_attempts = max_attempts

    async def chat(self, request: EngineeringChatRequest) -> EngineeringResponse:
        checked = _request(request)
        events = [_event(1, EngineeringEventType.AGENT_STARTED, "ENGINEERING_CHAT", "STARTED", 0, checked)]
        knowledge, knowledge_status = self._retrieve_knowledge(checked)
        events.append(
            _event(
                2,
                EngineeringEventType.AGENT_PROGRESS,
                "KNOWLEDGE_RETRIEVAL",
                knowledge_status,
                len(knowledge),
                checked,
            )
        )
        model_request = EngineeringModelRequest(
            request_id=checked.request_id,
            message=checked.message,
            context_summaries=_context_summaries(checked, knowledge),
            knowledge=knowledge,
        )
        output, attempts = await self._generate(model_request)
        events.append(
            _event(
                3,
                EngineeringEventType.AGENT_PROGRESS,
                "ENGINEERING_REASONING",
                "COMPLETED",
                attempts,
                checked,
            )
        )
        events.append(
            _event(
                4,
                EngineeringEventType.COMPLETED,
                "ENGINEERING_CHAT",
                "COMPLETED",
                1,
                checked,
            )
        )
        allowed_references = set(checked.context.reference_ids)
        allowed_references.update(
            reference
            for evidence in knowledge
            for reference in evidence.source_references
        )
        values = dict(
            request_id=checked.request_id,
            project_id=checked.project_id,
            requirement_analysis=output.requirement_analysis,
            architecture_recommendation=output.architecture_recommendation,
            hardware_suggestion=output.hardware_suggestion,
            risk_analysis=output.risk_analysis,
            next_action=output.next_action,
            reference_ids=tuple(
                item for item in output.reference_ids if item in allowed_references
            ),
            events=tuple(events),
        )
        return EngineeringResponse(
            **values,
            fingerprint=engineering_response_fingerprint(**values),
        )

    def _retrieve_knowledge(
        self,
        request: EngineeringChatRequest,
    ) -> tuple[tuple[KnowledgeEvidenceProjection, ...], str]:
        if self._knowledge is None:
            return (), "SKIPPED"
        try:
            candidate = self._knowledge.retrieve(
                request_id=request.request_id,
                query_summary=request.message,
            )
            if type(candidate) is not tuple:
                raise ValueError("knowledge projection is invalid")
            checked = tuple(_knowledge(item) for item in candidate)
            keys = tuple(item.evidence_id for item in checked)
            if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
                raise ValueError("knowledge projection is invalid")
            return checked, "COMPLETED"
        except Exception:
            return (), "UNAVAILABLE"

    async def _generate(
        self,
        request: EngineeringModelRequest,
    ) -> tuple[EngineeringModelOutput, int]:
        for attempt in range(1, self._max_attempts + 1):
            try:
                candidate = await self._model.generate(request.model_copy(deep=True))
                if type(candidate) is not EngineeringModelOutput:
                    raise ValueError("model output is invalid")
                return (
                    EngineeringModelOutput.model_validate(
                        candidate.model_copy(deep=True)
                    ),
                    attempt,
                )
            except Exception:
                if attempt == self._max_attempts:
                    raise AIModelUnavailable(
                        "engineering AI is unavailable"
                    ) from None
        raise AIModelUnavailable("engineering AI is unavailable") from None


class AIRuntime:
    __slots__ = ("_chat",)

    def __init__(self) -> None:
        raise TypeError("AIRuntime must be created by the factory")

    @classmethod
    def _compose(cls, chat: EngineeringChatPort) -> AIRuntime:
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_chat", chat)
        return runtime

    def engineering_chat_port(self) -> EngineeringChatPort:
        return self._chat


def _request(value: object) -> EngineeringChatRequest:
    if type(value) is not EngineeringChatRequest:
        raise AIRequestRejected("engineering chat request was rejected") from None
    try:
        return EngineeringChatRequest.model_validate(value.model_copy(deep=True))
    except (TypeError, ValueError, ValidationError):
        raise AIRequestRejected("engineering chat request was rejected") from None


def _knowledge(value: object) -> KnowledgeEvidenceProjection:
    if type(value) is not KnowledgeEvidenceProjection:
        raise ValueError("knowledge projection is invalid")
    return KnowledgeEvidenceProjection.model_validate(value.model_copy(deep=True))


def _context_summaries(
    request: EngineeringChatRequest,
    knowledge: tuple[KnowledgeEvidenceProjection, ...],
) -> tuple[str, ...]:
    context = request.context
    return (
        context.project_summary,
        f"Current engineering stage: {context.current_stage}",
        *(f"Decision: {item}" for item in context.decision_summaries),
        *(f"Verified knowledge: {item.summary}" for item in knowledge),
    )


def _event(
    sequence: int,
    event_type: EngineeringEventType,
    stage: str,
    status: str,
    count: int,
    request: EngineeringChatRequest,
) -> EngineeringEvent:
    values = dict(
        sequence=sequence,
        event_type=event_type,
        stage=stage,
        status=status,
        count=count,
        reference_id=request.request_id,
        timestamp=request.requested_at,
    )
    return EngineeringEvent(
        **values,
        fingerprint=engineering_event_fingerprint(**values),
    )


__all__ = ("AIRuntime", "_EngineeringChatService")

