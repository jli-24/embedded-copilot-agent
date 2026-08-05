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
    ComponentProjection,
    DesignComponent,
    DesignConnection,
    DesignModule,
    DesignSourceType,
    GPIOAssignment,
    GPIOAssignmentStatus,
    HardwareCapabilitySnapshot,
    HardwareDesignBlueprint,
    PowerTree,
    UnifiedHardwareModel,
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
    "DesignSourceType",
    "GPIOAssignment",
    "GPIOAssignmentStatus",
    "ComponentProjection",
    "HardwareCapabilitySnapshot",
    "HardwareDesignArtifact",
    "HardwareDesignBlueprint",
    "HardwareBlueprintProjectionAgentAdapter",
    "PowerTree",
    "UnifiedHardwareModel",
]
