"""Firmware Agent composition."""

from embedded_copilot.conversation.reasoning import ReasoningPort
from embedded_copilot.firmware_agent.facade import FirmwareAgent
from embedded_copilot.firmware_agent.generator import FirmwareReasoningGenerator
from embedded_copilot.firmware_agent.service import FirmwareAgentService


def create_firmware_agent(*, reasoning_port: ReasoningPort) -> FirmwareAgent:
    return FirmwareAgent(FirmwareAgentService(FirmwareReasoningGenerator(reasoning_port)))
