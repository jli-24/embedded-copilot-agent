"""Product-facing integration boundary for development adapters."""

from embedded_copilot.web_api.dev.integration.preparation import (
    DemoPreparationPort,
)
from embedded_copilot.web_api.dev.integration.product import (
    DemoProductWorkspacePort,
)
from embedded_copilot.web_api.dev.integration.repository import (
    InMemoryWebProjectRepository,
)
from embedded_copilot.web_api.dev.integration.v13 import (
    DemoBuildApprovalPort,
    DemoBuildExecutionPort,
    DemoFirmwareAgentPort,
    InMemoryWebProjectionRepository,
)

__all__ = (
    "DemoBuildApprovalPort",
    "DemoBuildExecutionPort",
    "DemoFirmwareAgentPort",
    "DemoPreparationPort",
    "DemoProductWorkspacePort",
    "InMemoryWebProjectRepository",
    "InMemoryWebProjectionRepository",
)
