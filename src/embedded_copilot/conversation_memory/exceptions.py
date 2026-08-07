class ConversationMemoryError(RuntimeError):
    """Base error for deterministic conversation memory extraction."""


class ConversationMemoryRejected(ConversationMemoryError):
    """The snapshot cannot produce a safe engineering candidate."""
