"""Firmware Agent facade."""

from embedded_copilot.firmware_agent.contracts import FirmwareAgentPort


class FirmwareAgent:
    __slots__ = ("_port",)

    def __init__(self, port: FirmwareAgentPort) -> None:
        self._port = port

    def firmware_agent_port(self) -> FirmwareAgentPort:
        return self._port
