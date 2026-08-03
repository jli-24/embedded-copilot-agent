"""Development-only deterministic Web Console adapters."""

from embedded_copilot.web_api.dev.attachment import DemoAttachmentProjectionPort
from embedded_copilot.web_api.dev.integration import (
    DemoBuildApprovalPort,
    DemoBuildExecutionPort,
    DemoFirmwareAgentPort,
    DemoPreparationPort,
    DemoProductWorkspacePort,
    InMemoryWebProjectionRepository,
    InMemoryWebProjectRepository,
)

__all__ = (
    "DemoAttachmentProjectionPort",
    "DemoBuildApprovalPort",
    "DemoBuildExecutionPort",
    "DemoFirmwareAgentPort",
    "DemoPreparationPort",
    "DemoProductWorkspacePort",
    "InMemoryWebProjectRepository",
    "InMemoryWebProjectionRepository",
)
