from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from embedded_copilot.conversation.context import ContextResolver
from embedded_copilot.conversation.models import (
    ConversationIntent,
    ConversationMessage,
    ConversationTurn,
    ReasoningOutput,
)
from embedded_copilot.conversation.repository import (
    ConversationNotFound,
    ConversationStateConflict,
    ProcessLocalConversationRepository,
)
from embedded_copilot.conversation.router import IntentRouter
from embedded_copilot.conversation.service import ConversationService
from embedded_copilot.copilot.session import create_session
from embedded_copilot.copilot.workspace import create_workspace
from embedded_copilot.copilot.models import (
    WorkspaceFileSource,
    WorkspaceFileStatus,
    WorkspaceFileType,
)
from embedded_copilot.copilot.workspace import WorkspaceFile, track_file
from embedded_copilot.intelligence.models import ModelResponse
from embedded_copilot.multimodal.context import (
    AttachmentBinding,
    AttachmentBindingNotFound,
    ProcessLocalAttachmentBindingRepository,
)
from embedded_copilot.multimodal.models import (
    MultimodalInput,
    MultimodalInputType,
)

UTC = timezone.utc
CREATED = datetime(2026, 7, 26, 8, 0, tzinfo=UTC)


def _workspace(session_id: str = "session:1"):
    return create_workspace(
        create_session(
            session_id=session_id,
            project_name="Security Terminal",
            user_requirement="Review an existing embedded design.",
            created_at=CREATED,
        )
    )


class _ReasoningPort:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...], str]] = []
        self.output = ReasoningOutput(
            response=ModelResponse(
                text="Candidate explanation requiring engineering validation.",
                metadata={"finish_reason": "deterministic"},
                source="test-reasoner",
            ),
            reasoning_chain=("REASONING_CHAIN_SENTINEL",),
            temporary_context=("TEMPORARY_CONTEXT_SENTINEL",),
        )

    async def reason(
        self,
        *,
        user_message_summary: str,
        context_summaries: tuple[str, ...],
        task_intent: str,
    ) -> ReasoningOutput:
        self.calls.append(
            (user_message_summary, context_summaries, task_intent)
        )
        return self.output


def _service(
    repository: ProcessLocalConversationRepository,
    reasoning: _ReasoningPort,
    attachments: ProcessLocalAttachmentBindingRepository | None = None,
) -> ConversationService:
    return ConversationService(
        repository=repository,
        context_resolver=ContextResolver(),
        intent_router=IntentRouter(),
        reasoning=reasoning,
        attachment_repository=attachments,
    )


@pytest.mark.parametrize(
    ("message", "expected"),
    (
        ("增加 MQ-2 and debug its startup error", ConversationIntent.ARTIFACT_CHANGE),
        ("Analyze this Guru Meditation log", ConversationIntent.DEBUG),
        ("Explain this ESP-IDF firmware task", ConversationIntent.FIRMWARE),
        ("Search the Datasheet knowledge", ConversationIntent.KNOWLEDGE),
        ("Summarize the next step", ConversationIntent.GENERAL),
    ),
)
def test_intent_router_uses_required_priority(
    message: str,
    expected: ConversationIntent,
) -> None:
    assert IntentRouter().route(message) is expected


def test_artifact_change_creates_handoff_without_mutation_or_model_call() -> None:
    repository = ProcessLocalConversationRepository()
    original = _workspace()
    repository.add(original)
    reasoning = _ReasoningPort()

    turn = asyncio.run(
        _service(repository, reasoning).send_message(
            ConversationMessage(
                session_id="session:1",
                message_id="message:1",
                content_summary="增加 MQ-2 for Engineering Agent review.",
                created_at=CREATED + timedelta(minutes=1),
            )
        )
    )

    updated = repository.get("session:1")
    assert turn.intent is ConversationIntent.ARTIFACT_CHANGE
    assert turn.handoff == "engineering_agent_review"
    assert reasoning.calls == []
    assert updated.session.artifact_ids == original.session.artifact_ids
    assert updated.session.decision_ids == original.session.decision_ids
    assert updated.session.approval_status == original.session.approval_status
    assert len(updated.messages) == 2


def test_reasoning_output_expiration() -> None:
    repository = ProcessLocalConversationRepository()
    repository.add(_workspace())
    reasoning = _ReasoningPort()

    turn = asyncio.run(
        _service(repository, reasoning).send_message(
            ConversationMessage(
                session_id="session:1",
                message_id="message:1",
                content_summary="Explain the available evidence conservatively.",
                created_at=CREATED + timedelta(minutes=1),
            )
        )
    )

    captured_context = reasoning.calls[0][1]
    assert not repository.contains(reasoning.output.response)
    assert not repository.contains(reasoning.output.reasoning_chain)
    assert not repository.contains(reasoning.output.temporary_context)
    assert not repository.contains(captured_context)
    assert turn.answer_summary == (
        "Candidate explanation requiring engineering validation."
    )
    serialized = repository.get("session:1").model_dump_json()
    assert "Reasoning suggestion returned for user review." in serialized
    assert "Candidate explanation requiring engineering validation." not in serialized
    assert "finish_reason" not in serialized
    assert "REASONING_CHAIN_SENTINEL" not in serialized
    assert "TEMPORARY_CONTEXT_SENTINEL" not in serialized


def test_new_repository_instance_cannot_recover_old_conversation() -> None:
    first = ProcessLocalConversationRepository()
    first.add(_workspace())

    second = ProcessLocalConversationRepository()

    with pytest.raises(ConversationNotFound, match="conversation was not found"):
        second.get("session:1")


def test_repository_is_bounded_and_returns_isolated_snapshots() -> None:
    repository = ProcessLocalConversationRepository(max_sessions=1, max_messages=2)
    source = _workspace()
    repository.add(source)

    snapshot = repository.get("session:1")
    assert snapshot is not source
    with pytest.raises(ConversationStateConflict, match="capacity"):
        repository.add(_workspace("session:2"))


def test_conversation_record_rejects_engineering_fact_fields() -> None:
    payload = ConversationTurn(
        session_id="session:1",
        intent=ConversationIntent.GENERAL,
        answer_summary="Safe response summary.",
        handoff="general_response",
    ).model_dump(mode="python")

    for forbidden_key in (
        "gpio",
        "component",
        "connection",
        "voltage",
        "current",
        "artifact_decision",
    ):
        with pytest.raises(ValidationError):
            ConversationTurn.model_validate({**payload, forbidden_key: "unsafe"})


def test_image_reference_routes_to_vision_with_session_bound_context() -> None:
    repository = ProcessLocalConversationRepository()
    workspace = track_file(
        _workspace(),
        WorkspaceFile(
            file_id="image:1",
            filename="schematic.png",
            file_type=WorkspaceFileType.OTHER,
            size_bytes=1024,
            source=WorkspaceFileSource.INPUT,
            status=WorkspaceFileStatus.REFERENCED,
            created_at=CREATED + timedelta(minutes=1),
        ),
    )
    repository.add(workspace)
    attachments = ProcessLocalAttachmentBindingRepository()
    attachments.bind(
        AttachmentBinding(
            session_id="session:1",
            input=MultimodalInput(
                type=MultimodalInputType.IMAGE,
                reference_id="image:1",
                summary="ESP32 schematic image reference.",
            ),
            basename="schematic.png",
            size_bytes=1024,
            created_at=CREATED + timedelta(minutes=1),
        )
    )
    reasoning = _ReasoningPort()

    turn = asyncio.run(
        _service(repository, reasoning, attachments).send_message(
            ConversationMessage(
                session_id="session:1",
                message_id="message:vision",
                content_summary="Review this ESP32 schematic image.",
                references=("image:1",),
                created_at=CREATED + timedelta(minutes=2),
            )
        )
    )

    message_summary, context_summaries, task_intent = reasoning.calls[0]
    assert turn.intent is ConversationIntent.VISION_ANALYSIS
    assert task_intent == "VISION_ANALYSIS"
    assert message_summary == "Review this ESP32 schematic image."
    assert "ESP32 schematic image reference." in context_summaries
    assert repository.get("session:1").messages[0].references == ("image:1",)


def test_conversation_rejects_reference_bound_to_another_session() -> None:
    repository = ProcessLocalConversationRepository()
    repository.add(_workspace())
    attachments = ProcessLocalAttachmentBindingRepository()
    attachments.bind(
        AttachmentBinding(
            session_id="session:2",
            input=MultimodalInput(
                type=MultimodalInputType.IMAGE,
                reference_id="image:1",
                summary="Another session image reference.",
            ),
            basename="private.png",
            size_bytes=128,
            created_at=CREATED + timedelta(minutes=1),
        )
    )

    with pytest.raises(AttachmentBindingNotFound):
        asyncio.run(
            _service(repository, _ReasoningPort(), attachments).send_message(
                ConversationMessage(
                    session_id="session:1",
                    message_id="message:cross-session",
                    content_summary="Review this image.",
                    references=("image:1",),
                    created_at=CREATED + timedelta(minutes=2),
                )
            )
        )
