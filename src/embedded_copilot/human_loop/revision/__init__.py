"""Revision context and proposal contracts."""

from embedded_copilot.human_loop.revision.context import (
    RevisionContext,
    RevisionContextReference,
    RevisionContextSource,
)
from embedded_copilot.human_loop.revision.proposal import (
    RevisionChange,
    RevisionGenerationRequest,
    RevisionPreparationRequest,
    RevisionProposal,
)

__all__ = (
    "RevisionChange",
    "RevisionContext",
    "RevisionContextReference",
    "RevisionContextSource",
    "RevisionGenerationRequest",
    "RevisionPreparationRequest",
    "RevisionProposal",
)
