from __future__ import annotations

from abc import ABC, abstractmethod

from embedded_copilot.agents.types import AgentResult, AgentTask


class BaseAgent(ABC):
    """Synchronous foundation contract for future domain agents."""

    name: str
    description: str
    capabilities: tuple[str, ...]

    @abstractmethod
    def run(self, task: AgentTask) -> AgentResult:
        """Execute one typed task and return one typed result."""
