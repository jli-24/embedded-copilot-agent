"""Safe exception hierarchy for the Supervisor Foundation pipeline."""


class SupervisorIntelligenceError(Exception):
    """Base error for deterministic Supervisor processing."""


class SupervisorAnalysisError(SupervisorIntelligenceError):
    """Raised when a request cannot be analyzed safely."""


class SupervisorPlanningError(SupervisorIntelligenceError):
    """Raised when a deterministic execution plan cannot be created."""


class SupervisorDispatchError(SupervisorIntelligenceError):
    """Raised when a planned Agent cannot be dispatched safely."""


class SupervisorAggregationError(SupervisorIntelligenceError):
    """Raised when Agent results cannot be aggregated safely."""
