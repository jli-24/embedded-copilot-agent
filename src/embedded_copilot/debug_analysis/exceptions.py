class DebugAnalysisError(RuntimeError):
    code = "DEBUG_UNAVAILABLE"


class DebugAnalysisUnavailable(DebugAnalysisError):
    code = "DEBUG_UNAVAILABLE"


class DebugAnalysisRejected(DebugAnalysisError):
    code = "DEBUG_REJECTED"
