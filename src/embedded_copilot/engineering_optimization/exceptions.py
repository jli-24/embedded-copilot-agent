class OptimizationAnalysisError(RuntimeError):
    code = "OPTIMIZATION_UNAVAILABLE"


class OptimizationUnavailable(OptimizationAnalysisError):
    code = "OPTIMIZATION_UNAVAILABLE"


class OptimizationRejected(OptimizationAnalysisError):
    code = "OPTIMIZATION_REJECTED"


class FindingNotFound(OptimizationAnalysisError):
    code = "FINDING_NOT_FOUND"


class ApprovalRequired(OptimizationAnalysisError):
    code = "APPROVAL_REQUIRED"


__all__ = [
    "ApprovalRequired",
    "FindingNotFound",
    "OptimizationAnalysisError",
    "OptimizationRejected",
    "OptimizationUnavailable",
]
