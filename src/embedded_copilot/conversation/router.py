from __future__ import annotations

from embedded_copilot.conversation.models import ConversationIntent
from embedded_copilot.intelligence._validation import safe_text

_ARTIFACT_CHANGE_TERMS = (
    "增加",
    "添加",
    "修改",
    "删除",
    "add ",
    "change ",
    "modify ",
    "remove ",
)
_DEBUG_TERMS = ("debug", "error", "fault", "guru meditation", "log", "crash")
_FIRMWARE_TERMS = ("firmware", "esp-idf", "stm32 hal", "freertos", "code")
_KNOWLEDGE_TERMS = ("knowledge", "datasheet", "document", "search", "retrieve")


class IntentRouter:
    def route(self, message_summary: str) -> ConversationIntent:
        message = safe_text(
            message_summary,
            field="message_summary",
            max_length=512,
        ).casefold()
        if any(term in message for term in _ARTIFACT_CHANGE_TERMS):
            return ConversationIntent.ARTIFACT_CHANGE
        if any(term in message for term in _DEBUG_TERMS):
            return ConversationIntent.DEBUG
        if any(term in message for term in _FIRMWARE_TERMS):
            return ConversationIntent.FIRMWARE
        if any(term in message for term in _KNOWLEDGE_TERMS):
            return ConversationIntent.KNOWLEDGE
        return ConversationIntent.GENERAL
