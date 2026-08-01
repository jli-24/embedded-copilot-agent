"""Human-review approval binding for controlled execution."""

from embedded_copilot.execution_runtime.approval.context import (
    ExecutionApprovalContext,
    execution_approval_fingerprint,
)

__all__ = ("ExecutionApprovalContext", "execution_approval_fingerprint")
