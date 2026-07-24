from __future__ import annotations

import copy

from embedded_copilot.knowledge.models import KnowledgeQuery
from embedded_copilot.supervisor.models import SupervisorTask


_AGENT_DOMAINS = {
    "FirmwareAgent": "firmware",
    "HardwareAgent": "hardware",
    "PCBAgent": "pcb",
    "DebugAgent": "debug",
}
_KEYWORD_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ESP32", ("esp32", "esp-idf")),
    ("STM32", ("stm32", "stm32 hal")),
    ("ESP-IDF", ("esp-idf",)),
    ("STM32 HAL", ("stm32 hal", " hal ")),
    ("FreeRTOS", ("freertos",)),
    ("Camera", ("camera", "ov2640")),
    ("OV2640", ("camera", "ov2640")),
    ("GPIO", ("camera", "sensor", "gpio")),
    ("Power", ("camera", "sensor", "power")),
    ("UART", ("uart",)),
    ("SPI", ("spi",)),
    ("I2C", ("i2c", "i²c")),
    ("WiFi", ("wifi", "wi-fi")),
    ("HardFault", ("hard fault", "hardfault")),
    ("Compile Error", ("compile error",)),
    ("Communication Error", ("communication error",)),
    ("Crash", ("crash",)),
    ("Watchdog", ("watchdog",)),
)
_SUBJECTS = (
    "Camera",
    "HardFault",
    "Compile Error",
    "Communication Error",
    "Crash",
    "Power",
    "UART",
    "SPI",
    "I2C",
    "WiFi",
)


def _stable_unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


class KnowledgeQueryBuilder:
    """Build an allowlisted deterministic query from a parsed Supervisor task."""

    def build(self, task: SupervisorTask) -> KnowledgeQuery:
        if not isinstance(task, SupervisorTask):
            raise TypeError("task must be a SupervisorTask")
        isolated = SupervisorTask.model_validate(
            copy.deepcopy(task.model_dump(mode="python"))
        )
        source = f" {isolated.request.casefold()} "
        keywords = _stable_unique(
            [
                keyword
                for keyword, markers in _KEYWORD_RULES
                if any(marker in source for marker in markers)
            ]
        )
        domains = _stable_unique(
            [
                _AGENT_DOMAINS[agent]
                for agent in isolated.required_agents
                if agent in _AGENT_DOMAINS
            ]
        )
        platform = next(
            (value for value in ("ESP32", "STM32") if value in keywords),
            None,
        )
        subject = next((value for value in _SUBJECTS if value in keywords), None)
        topic_parts = [part for part in (platform, subject) if part]
        if not topic_parts:
            topic_parts = ["Embedded", "Engineering"]
        topic = " ".join(topic_parts)
        query_terms = _stable_unique([*topic_parts, *keywords, *domains])
        return KnowledgeQuery(
            query=" ".join(query_terms),
            sources=[],
            top_k=4,
            metadata={
                "topic": topic,
                "keywords": keywords,
                "domains": domains,
            },
        )
