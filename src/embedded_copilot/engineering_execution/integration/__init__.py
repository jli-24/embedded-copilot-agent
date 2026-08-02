"""Typed integrations for external engineering contracts."""

from embedded_copilot.engineering_execution.integration.inputs import (
    BuildExecutionInput,
    DebugExecutionInput,
    EngineeringExecutionRequest,
    FlashExecutionInput,
    build_execution_input_fingerprint,
    debug_execution_input_fingerprint,
    engineering_execution_request_fingerprint,
    flash_execution_input_fingerprint,
)

__all__ = (
    "BuildExecutionInput",
    "DebugExecutionInput",
    "EngineeringExecutionRequest",
    "FlashExecutionInput",
    "build_execution_input_fingerprint",
    "debug_execution_input_fingerprint",
    "engineering_execution_request_fingerprint",
    "flash_execution_input_fingerprint",
)
