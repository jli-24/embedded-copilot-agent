"""Structured failures for the read-only knowledge graph boundary."""


class EngineeringKnowledgeError(Exception):
    """Base error for deterministic graph projection and retrieval."""


class EngineeringKnowledgeProjectionRejected(EngineeringKnowledgeError):
    """The input cannot be projected as approved graph knowledge."""


class EngineeringKnowledgeUnavailable(EngineeringKnowledgeError):
    """A required graph projection is unavailable."""


__all__ = (
    "EngineeringKnowledgeError",
    "EngineeringKnowledgeProjectionRejected",
    "EngineeringKnowledgeUnavailable",
)
