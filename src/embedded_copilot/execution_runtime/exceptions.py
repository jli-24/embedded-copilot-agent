"""Sanitized exceptions for the Execution Integration Runtime."""


class ExecutionError(Exception):
    """Base class for safe execution-boundary failures."""


class ExecutionUnavailable(ExecutionError):
    """A configured execution dependency is unavailable."""


class ExecutionRejected(ExecutionError):
    """The execution contract, binding, or replay was rejected."""


class ExecutionTimeout(ExecutionError):
    """A controlled executor timed out."""


class ExecutionVerificationFailed(ExecutionError):
    """The result verification boundary failed."""


class ExecutionProgressUnavailable(ExecutionError):
    """A required progress event could not be delivered."""
