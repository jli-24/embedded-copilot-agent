"""Framework-independent deterministic engineering verification foundation."""

from embedded_copilot.verification_agent.agent import VerificationAgent
from embedded_copilot.verification_agent.checks import (
    FirmwareVerificationChecker,
    HardwareConstraintChecker,
    ToolResultChecker,
)
from embedded_copilot.verification_agent.exceptions import (
    VerificationAgentError,
    VerificationAuditUnavailable,
    VerificationCheckerUnavailable,
    VerificationRequestRejected,
)
from embedded_copilot.verification_agent.factory import create_verification_agent
from embedded_copilot.verification_agent.models import (
    FirmwareResourceUsage,
    FirmwareVerificationSubject,
    HardwareVerificationSubject,
    InterfaceBindingCandidate,
    PowerConnectionCandidate,
    ToolResultVerificationSubject,
    VerificationAuditEvent,
    VerificationAuditEventType,
    VerificationCheckResult,
    VerificationFinding,
    VerificationFindingCategory,
    VerificationRequest,
    VerificationResult,
    VerificationSeverity,
    VerificationStatus,
    VerificationSubject,
    VerificationSubjectType,
)
from embedded_copilot.verification_agent.ports import (
    VerificationAuditSink,
    VerificationCheckerPort,
    VerificationPort,
)

__all__ = (
    "FirmwareResourceUsage",
    "FirmwareVerificationChecker",
    "FirmwareVerificationSubject",
    "HardwareConstraintChecker",
    "HardwareVerificationSubject",
    "InterfaceBindingCandidate",
    "PowerConnectionCandidate",
    "ToolResultChecker",
    "ToolResultVerificationSubject",
    "VerificationAgent",
    "VerificationAgentError",
    "VerificationAuditEvent",
    "VerificationAuditEventType",
    "VerificationAuditSink",
    "VerificationAuditUnavailable",
    "VerificationCheckResult",
    "VerificationCheckerPort",
    "VerificationCheckerUnavailable",
    "VerificationFinding",
    "VerificationFindingCategory",
    "VerificationPort",
    "VerificationRequest",
    "VerificationRequestRejected",
    "VerificationResult",
    "VerificationSeverity",
    "VerificationStatus",
    "VerificationSubject",
    "VerificationSubjectType",
    "create_verification_agent",
)
