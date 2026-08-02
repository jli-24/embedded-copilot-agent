"""Framework-independent, proposal-only Hardware Engineering Layer."""

from embedded_copilot.engineering_hardware.contracts import HardwareEngineeringPort
from embedded_copilot.engineering_hardware.exceptions import (
    HardwareEngineeringError,
    HardwareEngineeringRejected,
)
from embedded_copilot.engineering_hardware.facade import EngineeringHardwareRuntime
from embedded_copilot.engineering_hardware.factory import (
    create_engineering_hardware_runtime,
)
from embedded_copilot.engineering_hardware.integration.intelligence import (
    HardwareEngineeringRequest,
)
from embedded_copilot.engineering_hardware.models import (
    BOMLineItem,
    BOMProposal,
    ComponentSelectionItem,
    ComponentSelectionProposal,
    ComponentSelectionStatus,
    HardwareDesignReviewProjection,
    HardwareEngineeringProposal,
    HardwareEvidenceTrace,
    HardwareFindingCode,
    HardwareFindingSeverity,
    HardwareProposalItemStatus,
    HardwareReviewFinding,
    InterfaceContract,
    InterfaceContractProposal,
    InterfaceContractStatus,
    PCBConstraint,
    PCBConstraintCategory,
    PCBConstraintProposal,
    PowerDesignProposal,
    SchematicIntentModel,
    SystemArchitectureBlock,
    SystemArchitectureProposal,
    SystemArchitectureRelation,
    hardware_engineering_proposal_fingerprint,
)

__all__ = (
    "BOMLineItem",
    "BOMProposal",
    "ComponentSelectionItem",
    "ComponentSelectionProposal",
    "ComponentSelectionStatus",
    "EngineeringHardwareRuntime",
    "HardwareDesignReviewProjection",
    "HardwareEngineeringError",
    "HardwareEngineeringPort",
    "HardwareEngineeringProposal",
    "HardwareEngineeringRejected",
    "HardwareEngineeringRequest",
    "HardwareEvidenceTrace",
    "HardwareFindingCode",
    "HardwareFindingSeverity",
    "HardwareProposalItemStatus",
    "HardwareReviewFinding",
    "InterfaceContract",
    "InterfaceContractProposal",
    "InterfaceContractStatus",
    "PCBConstraint",
    "PCBConstraintCategory",
    "PCBConstraintProposal",
    "PowerDesignProposal",
    "SchematicIntentModel",
    "SystemArchitectureBlock",
    "SystemArchitectureProposal",
    "SystemArchitectureRelation",
    "create_engineering_hardware_runtime",
    "hardware_engineering_proposal_fingerprint",
)
