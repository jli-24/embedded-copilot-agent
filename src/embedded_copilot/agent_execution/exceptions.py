"""Sanitized Agent Execution Runtime exceptions."""


class AgentExecutionError(Exception):
    """Base exception for rejected execution boundary operations."""


class AgentExecutionRejected(AgentExecutionError):
    """Raised when a typed execution input cannot be trusted."""


class ExecutionRecoveryRejected(AgentExecutionError):
    """Raised when a recovery request is invalid or cannot be replayed."""


class ExecutionProgressUnavailable(AgentExecutionError):
    """Raised when progress cannot be delivered safely."""
