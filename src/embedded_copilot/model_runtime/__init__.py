"""Framework-independent model runtime infrastructure."""

from embedded_copilot.model_runtime.composition.runtime import create_model_runtime
from embedded_copilot.model_runtime.facade import ModelRuntime

__all__ = ["ModelRuntime", "create_model_runtime"]
