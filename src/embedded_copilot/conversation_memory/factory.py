from .service import ConversationMemoryService


def create_conversation_memory() -> ConversationMemoryService:
    return ConversationMemoryService()


__all__ = ["create_conversation_memory"]
