from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import Field

from embedded_copilot.schemas.result import ContractModel


class ExtractedEntities(ContractModel):
    chip: str | None = None
    protocols: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)


EntityKind = Literal["chip", "protocol", "framework", "feature"]


@dataclass(frozen=True, slots=True)
class _EntityRule:
    kind: EntityKind
    canonical: str
    pattern: re.Pattern[str]


def _rule(kind: EntityKind, canonical: str, pattern: str) -> _EntityRule:
    return _EntityRule(kind, canonical, re.compile(pattern, re.IGNORECASE))


_RULES = (
    _rule("chip", "ESP32-S3", r"(?<![A-Z0-9])ESP32[\s-]?S3(?![A-Z0-9])"),
    _rule("chip", "ESP32-C3", r"(?<![A-Z0-9])ESP32[\s-]?C3(?![A-Z0-9])"),
    _rule("chip", "STM32F103", r"(?<![A-Z0-9])STM32F103[A-Z0-9]*"),
    _rule("protocol", "SPI", r"\bSPI\b"),
    _rule("protocol", "UART", r"\bUART\b"),
    _rule("protocol", "I2C", r"\bI2C\b"),
    _rule("framework", "ESP-IDF", r"\bESP[\s-]?IDF\b"),
    _rule("framework", "STM32 HAL", r"\bSTM32\s+HAL\b"),
    _rule("framework", "FreeRTOS", r"\bFreeRTOS\b"),
    _rule("feature", "DMA", r"\bDMA\b"),
)


class EmbeddedEntityExtractor:
    def extract(self, query: str) -> ExtractedEntities:
        matches: list[tuple[int, int, _EntityRule]] = []
        for rule_index, rule in enumerate(_RULES):
            matches.extend(
                (match.start(), rule_index, rule)
                for match in rule.pattern.finditer(query)
            )
        matches.sort(key=lambda item: (item[0], item[1]))

        chip: str | None = None
        protocols: list[str] = []
        frameworks: list[str] = []
        features: list[str] = []
        seen_protocols: set[str] = set()
        seen_frameworks: set[str] = set()
        seen_features: set[str] = set()

        for _, _, rule in matches:
            if rule.kind == "chip":
                if chip is None:
                    chip = rule.canonical
                continue
            if rule.kind == "protocol" and rule.canonical not in seen_protocols:
                seen_protocols.add(rule.canonical)
                protocols.append(rule.canonical)
            if rule.kind == "framework" and rule.canonical not in seen_frameworks:
                seen_frameworks.add(rule.canonical)
                frameworks.append(rule.canonical)
            if rule.canonical not in seen_features:
                seen_features.add(rule.canonical)
                features.append(rule.canonical)

        return ExtractedEntities(
            chip=chip,
            protocols=protocols,
            frameworks=frameworks,
            features=features,
        )
