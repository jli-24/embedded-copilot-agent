from __future__ import annotations

import pytest

from embedded_copilot.knowledge.entity import EmbeddedEntityExtractor


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("ESP32-S3 SPI", "ESP32-S3"),
        ("esp32 c3 UART", "ESP32-C3"),
        ("STM32F103C8T6 I2C", "STM32F103"),
    ],
)
def test_entity_extractor_recognizes_supported_chips(
    query: str,
    expected: str,
) -> None:
    assert EmbeddedEntityExtractor().extract(query).chip == expected


def test_entity_extractor_classifies_protocols_frameworks_and_dma() -> None:
    entities = EmbeddedEntityExtractor().extract(
        "ESP-IDF SPI DMA with STM32 HAL UART and FreeRTOS I2C"
    )

    assert entities.protocols == ["SPI", "UART", "I2C"]
    assert entities.frameworks == ["ESP-IDF", "STM32 HAL", "FreeRTOS"]
    assert entities.features == [
        "ESP-IDF",
        "SPI",
        "DMA",
        "STM32 HAL",
        "UART",
        "FreeRTOS",
        "I2C",
    ]


def test_entity_extractor_preserves_first_occurrence_and_deduplicates() -> None:
    entities = EmbeddedEntityExtractor().extract(
        "dma SPI spi I2C DMA freertos FreeRTOS"
    )

    assert entities.protocols == ["SPI", "I2C"]
    assert entities.frameworks == ["FreeRTOS"]
    assert entities.features == ["DMA", "SPI", "I2C", "FreeRTOS"]


def test_entity_extractor_matches_example_contract() -> None:
    entities = EmbeddedEntityExtractor().extract("ESP32-S3 SPI DMA")

    assert entities.chip == "ESP32-S3"
    assert entities.features == ["SPI", "DMA"]


def test_entity_extractor_returns_empty_result_for_unknown_query() -> None:
    entities = EmbeddedEntityExtractor().extract("unrelated cooking recipe")

    assert entities.chip is None
    assert entities.protocols == []
    assert entities.frameworks == []
    assert entities.features == []
