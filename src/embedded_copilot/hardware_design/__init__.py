"""Read-only hardware design explanation contracts."""

from embedded_copilot.hardware_design.approval import (
    DesignApproval,
    DesignApprovalStatus,
)
from embedded_copilot.hardware_design.adapter import (
    HardwareBlueprintProjectionAgentAdapter,
)
from embedded_copilot.hardware_design.artifact import HardwareDesignArtifact
from embedded_copilot.hardware_design.decision import (
    DesignDecision,
    DesignDecisionStatus,
)
from embedded_copilot.hardware_design.evidence import (
    DesignEvidence,
    DesignEvidenceSourceType,
)
from embedded_copilot.hardware_design.models import (
    DesignComponent,
    DesignConnection,
    DesignModule,
    GPIOAssignment,
    GPIOAssignmentStatus,
    HardwareDesignBlueprint,
    PowerTree,
)

__all__ = [
    "DesignApproval",
    "DesignApprovalStatus",
    "DesignComponent",
    "DesignConnection",
    "DesignDecision",
    "DesignDecisionStatus",
    "DesignEvidence",
    "DesignEvidenceSourceType",
    "DesignModule",
    "GPIOAssignment",
    "GPIOAssignmentStatus",
    "HardwareDesignArtifact",
    "HardwareDesignBlueprint",
    "HardwareBlueprintProjectionAgentAdapter",
    "PowerTree",
]
