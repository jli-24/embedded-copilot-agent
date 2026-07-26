from __future__ import annotations

import copy
import hashlib

from embedded_copilot.conversation.context import ContextResolver
from embedded_copilot.conversation.models import (
    ConversationIntent,
    ConversationMessage,
    ConversationTurn,
    ReasoningOutput,
)
from embedded_copilot.conversation.reasoning import ReasoningPort
from embedded_copilot.conversation.repository import ConversationRepository
from embedded_copilot.conversation.router import IntentRouter
from embedded_copilot.context_runtime.contracts import (
    EngineeringContextPort,
    EngineeringContextRequest,
    EngineeringContextResponse,
)
from embedded_copilot.context_runtime.exceptions import EngineeringContextConflict
from embedded_copilot.copilot.context import ChatMessage
from embedded_copilot.copilot.models import ChatRole
from embedded_copilot.copilot.workspace import record_message
from embedded_copilot.multimodal.context import (
    AttachmentBinding,
    AttachmentBindingNotFound,
    AttachmentBindingRepository,
)

_HANDOFFS = {
    ConversationIntent.ARTIFACT_CHANGE: "engineering_agent_review",
    ConversationIntent.CHAT: "general_response",
    ConversationIntent.DEBUG: "debug_agent_review",
    ConversationIntent.VISION_ANALYSIS: "engineering_agent_review",
    ConversationIntent.DATASHEET_ANALYSIS: "knowledge_review",
    ConversationIntent.DESIGN_REVIEW: "engineering_agent_review",
    ConversationIntent.FIRMWARE: "firmware_agent_review",
    ConversationIntent.KNOWLEDGE: "knowledge_review",
    ConversationIntent.GENERAL: "general_response",
}
_CHANGE_HANDOFF_SUMMARY = (
    "Change intent recorded for independent Engineering Agent validation."
)
_REASONING_RECORD_SUMMARY = "Reasoning suggestion returned for user review."


class ConversationService:
    def __init__(
        self,
        *,
        repository: ConversationRepository,
        context_resolver: ContextResolver,
        intent_router: IntentRouter,
        reasoning: ReasoningPort,
        context_port: EngineeringContextPort,
        attachment_repository: AttachmentBindingRepository | None = None,
    ) -> None:
        self._repository = repository
        self._context_resolver = context_resolver
        self._intent_router = intent_router
        self._reasoning = reasoning
        self._context_port = context_port
        self._attachment_repository = attachment_repository

    async def send_message(self, message: ConversationMessage) -> ConversationTurn:
        isolated_message = ConversationMessage.model_validate(
            copy.deepcopy(message.model_dump(mode="python"))
        )
        workspace = self._repository.get(isolated_message.session_id)
        bindings = self._resolve_bindings(isolated_message)
        intent = self._intent_router.route(
            isolated_message.content_summary,
            reference_types=tuple(item.input.type for item in bindings),
        )

        if intent is ConversationIntent.ARTIFACT_CHANGE:
            answer_summary = _CHANGE_HANDOFF_SUMMARY
            persisted_summary = _CHANGE_HANDOFF_SUMMARY
        else:
            raw_context = await self._context_port.compose(
                EngineeringContextRequest(
                    session_id=isolated_message.session_id,
                    task_intent=intent.value,
                    reference_ids=isolated_message.references,
                )
            )
            context = EngineeringContextResponse.model_validate(
                copy.deepcopy(raw_context.model_dump(mode="python"))
            )
            if context.context_summary.task_intent != intent.value:
                raise EngineeringContextConflict()
            model_input = self._context_resolver.resolve(
                workspace,
                isolated_message.content_summary,
                reference_summaries=_context_summaries(context),
            )
            raw_output = await self._reasoning.reason(
                user_message_summary=model_input.message_summary,
                context_summaries=model_input.context_summaries,
                task_intent=intent.value,
            )
            output = ReasoningOutput.model_validate(
                copy.deepcopy(raw_output.model_dump(mode="python"))
            )
            answer_summary = " ".join(output.response.text.split())[:512]
            persisted_summary = _REASONING_RECORD_SUMMARY

        user_message = ChatMessage(
            message_id=isolated_message.message_id,
            role=ChatRole.USER,
            content_summary=isolated_message.content_summary,
            created_at=isolated_message.created_at,
            references=isolated_message.references,
        )
        assistant_message = ChatMessage(
            message_id=_assistant_message_id(
                isolated_message.session_id,
                isolated_message.message_id,
            ),
            role=ChatRole.ASSISTANT,
            content_summary=persisted_summary,
            created_at=isolated_message.created_at,
            references=isolated_message.references,
        )
        updated = record_message(workspace, user_message)
        updated = record_message(updated, assistant_message)
        self._repository.save(updated)
        return ConversationTurn(
            session_id=isolated_message.session_id,
            intent=intent,
            answer_summary=answer_summary,
            handoff=_HANDOFFS[intent],
        )

    def _resolve_bindings(
        self,
        message: ConversationMessage,
    ) -> tuple[AttachmentBinding, ...]:
        if not message.references:
            return ()
        if self._attachment_repository is None:
            raise AttachmentBindingNotFound(
                "attachment reference repository is unavailable"
            )
        return tuple(
            self._attachment_repository.get(message.session_id, reference)
            for reference in message.references
        )


def _assistant_message_id(session_id: str, message_id: str) -> str:
    digest = hashlib.sha256(f"{session_id}:{message_id}".encode()).hexdigest()[:24]
    return f"reply:{digest}"


def _context_summaries(
    response: EngineeringContextResponse,
) -> tuple[str, ...]:
    summary = response.context_summary
    projected = [f"Task intent: {summary.task_intent}."]
    for datasheet in summary.datasheets:
        component = datasheet.component_candidate
        component_text = "no component candidate"
        if component is not None:
            label = (
                f"{component.family}/{component.model}"
                if component.model is not None
                else component.family
            )
            component_text = f"component candidate {label}"
        interfaces = ", ".join(item.name for item in datasheet.interfaces) or "none"
        sections = ", ".join(item.name for item in datasheet.sections) or "none"
        projected.append(
            f"Datasheet candidate {datasheet.file_id}: {component_text}; "
            f"interface candidates {interfaces}; section candidates {sections}."
        )
    for file_context in summary.files:
        if file_context.page_count is not None:
            statistics = f"{file_context.page_count} pages"
        else:
            statistics = (
                f"{file_context.line_count} lines, "
                f"{file_context.character_count} characters"
            )
        projected.append(
            f"File context {file_context.file_id}: "
            f"{file_context.document_type.value}, {statistics}."
        )
    projected.extend(
        f"Vision reference {item.reference_id}: {item.image_type.value}."
        for item in summary.vision
    )
    return tuple(projected)
