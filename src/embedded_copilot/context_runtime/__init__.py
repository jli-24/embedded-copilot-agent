"""Framework-independent engineering context contracts and facade."""

from embedded_copilot.context_runtime.contracts import EngineeringContextPort
from embedded_copilot.context_runtime.facade import EngineeringContextRuntime

__all__ = [
    "EngineeringContextPort",
    "EngineeringContextRuntime",
]
