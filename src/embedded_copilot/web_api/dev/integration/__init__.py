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

__all__ = (
    "DemoPreparationPort",
    "DemoProductWorkspacePort",
    "InMemoryWebProjectRepository",
)
