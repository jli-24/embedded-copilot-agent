from __future__ import annotations

from embedded_copilot.agents.base import BaseAgent


class AgentRegistry:
    """In-memory registry for foundation agent instances."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent) -> None:
        name = agent.name.strip()
        if not name:
            raise ValueError("agent name must not be empty")
        if name in self._agents:
            raise ValueError(f"agent already registered: {name}")
        self._agents[name] = agent

    def get_agent(self, name: str) -> BaseAgent:
        return self._agents[name.strip()]

    def list_agents(self) -> list[str]:
        return list(self._agents)
