from __future__ import annotations

import re

from pydantic import ValidationError

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.firmware.exceptions import FirmwareGenerationError
from embedded_copilot.firmware.generator import FirmwareGenerator
from embedded_copilot.firmware.models import FirmwareRequest
from embedded_copilot.firmware.validator import FirmwareValidator


_PLATFORMS = ("ESP32", "STM32")
_FRAMEWORKS = ("ESP-IDF", "FreeRTOS", "HAL")
_PERIPHERALS = ("GPIO", "WiFi", "UART", "SPI", "ADC")


def _find_first(text: str, candidates: tuple[str, ...]) -> str | None:
    matches: list[tuple[int, str]] = []
    for candidate in candidates:
        match = re.search(
            rf"(?<![A-Za-z0-9]){re.escape(candidate)}(?![A-Za-z0-9])",
            text,
            re.IGNORECASE,
        )
        if match is not None:
            matches.append((match.start(), candidate))
    return min(matches)[1] if matches else None


def _find_all(text: str, candidates: tuple[str, ...]) -> list[str]:
    matches: list[tuple[int, str]] = []
    for candidate in candidates:
        match = re.search(
            rf"(?<![A-Za-z0-9]){re.escape(candidate)}(?![A-Za-z0-9])",
            text,
            re.IGNORECASE,
        )
        if match is not None:
            matches.append((match.start(), candidate))
    return [candidate for _, candidate in sorted(matches)]


class FirmwareAgent(BaseAgent):
    """Foundation-only deterministic firmware request orchestrator."""

    name = "FirmwareAgent"
    description = "Validates firmware requests and produces unverified mock code."
    capabilities = ("code_generation", "platform_check")

    def __init__(
        self,
        *,
        generator: FirmwareGenerator | None = None,
        validator: FirmwareValidator | None = None,
    ) -> None:
        self._generator = generator or FirmwareGenerator()
        self._validator = validator or FirmwareValidator()

    def run(self, task: AgentTask) -> AgentResult:
        try:
            request = self._to_firmware_request(task)
            generated = self._generator.generate(request)
            validation = self._validator.validate(generated)
            validation_payload = validation.model_dump(mode="json")
            if not validation.success:
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.ERROR,
                    output="; ".join(validation.errors),
                    metadata={"validation": validation_payload},
                )
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                output=generated.model_dump_json(),
                metadata={"validation": validation_payload},
            )
        except (FirmwareGenerationError, ValidationError, ValueError) as exc:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                output=str(exc) or "firmware request failed",
                metadata={"error_type": type(exc).__name__},
            )

    @staticmethod
    def _to_firmware_request(task: AgentTask) -> FirmwareRequest:
        platform = task.metadata.get("platform")
        if platform is None:
            platform = _find_first(task.requirement, _PLATFORMS)
        if platform is None:
            raise ValueError("firmware platform is required")

        framework = task.metadata.get("framework")
        if framework is None:
            framework = _find_first(task.requirement, _FRAMEWORKS)

        peripherals = task.metadata.get("peripherals")
        if peripherals is None:
            peripherals = _find_all(task.requirement, _PERIPHERALS)

        return FirmwareRequest(
            requirement=task.requirement,
            platform=platform,
            framework=framework,
            peripherals=peripherals,
            metadata=dict(task.metadata),
        )
