"""Sanitized Workflow Runtime failures."""


class WorkflowRuntimeError(RuntimeError):
    """Base class for safe Workflow Runtime failures."""


class WorkflowAgentUnavailable(WorkflowRuntimeError):
    """A required planning boundary was unavailable or invalid."""


class WorkflowContextUnavailable(WorkflowRuntimeError):
    """The trusted context projection boundary was unavailable."""


class WorkflowRiskRejected(WorkflowRuntimeError):
    """A projected risk was not safely bound to verified context."""


class WorkflowDAGRejected(WorkflowRuntimeError):
    """The proposed task graph was invalid."""


class WorkflowApprovalRejected(WorkflowRuntimeError):
    """The approval did not bind to the waiting workflow snapshot."""


class WorkflowProgressUnavailable(WorkflowRuntimeError):
    """A required progress event could not be delivered."""
