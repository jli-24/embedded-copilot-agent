class OptimizationError(RuntimeError):
    code = "OPTIMIZATION_UNAVAILABLE"


class OptimizationUnavailable(OptimizationError):
    code = "OPTIMIZATION_UNAVAILABLE"


class ProposalNotFound(OptimizationError):
    code = "PROPOSAL_NOT_FOUND"


class OptimizationRejected(OptimizationError):
    code = "PROPOSAL_REJECTED"


class OptimizationApprovalRequired(OptimizationError):
    code = "APPROVAL_REQUIRED"
