from embedded_copilot.reasoning_runtime.analysis import CanonicalReasoningPort
from embedded_copilot.reasoning_runtime.contracts import ReasoningPort
from embedded_copilot.reasoning_runtime.facade import ReasoningRuntime


def create_reasoning_runtime() -> ReasoningRuntime:
    port: ReasoningPort = CanonicalReasoningPort()
    return ReasoningRuntime._compose(port)
