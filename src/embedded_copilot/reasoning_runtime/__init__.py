"""Framework-independent deterministic reasoning contracts and facade."""

from embedded_copilot.reasoning_runtime.composition import create_reasoning_runtime
from embedded_copilot.reasoning_runtime.contracts import (
    CapabilityEntry,
    NextStep,
    ReasoningContextSnapshot,
    ReasoningPort,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningSummary,
    ReasoningTrace,
    RiskCandidate,
    RuleResult,
    SourceType,
    SupportingReference,
)
from embedded_copilot.reasoning_runtime.exceptions import (
    ReasoningAnalysisTimeout,
    ReasoningContextConflict,
    ReasoningContextNotFound,
    ReasoningError,
    ReasoningRequestRejected,
    ReasoningRuntimeUnavailable,
)
from embedded_copilot.reasoning_runtime.facade import ReasoningRuntime
from embedded_copilot.reasoning_runtime.snapshot import (
    build_reasoning_context_snapshot,
)

__all__ = [
    "CapabilityEntry",
    "NextStep",
    "ReasoningAnalysisTimeout",
    "ReasoningContextConflict",
    "ReasoningContextNotFound",
    "ReasoningContextSnapshot",
    "ReasoningError",
    "ReasoningPort",
    "ReasoningRequest",
    "ReasoningRequestRejected",
    "ReasoningResponse",
    "ReasoningRuntime",
    "ReasoningRuntimeUnavailable",
    "ReasoningSummary",
    "ReasoningTrace",
    "RiskCandidate",
    "RuleResult",
    "SourceType",
    "SupportingReference",
    "build_reasoning_context_snapshot",
    "create_reasoning_runtime",
]
