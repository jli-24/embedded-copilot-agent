"""Development-only deterministic Web Console adapters."""

from embedded_copilot.web_api.dev.attachment import DemoAttachmentProjectionPort
from embedded_copilot.web_api.dev.integration import (
    DemoPreparationPort,
    DemoProductWorkspacePort,
    InMemoryWebProjectRepository,
)

__all__ = (
    "DemoAttachmentProjectionPort",
    "DemoPreparationPort",
    "DemoProductWorkspacePort",
    "InMemoryWebProjectRepository",
)
