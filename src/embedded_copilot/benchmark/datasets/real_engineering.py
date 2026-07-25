from __future__ import annotations

from embedded_copilot.benchmark.dataset import BenchmarkDataset
from embedded_copilot.benchmark.models import BenchmarkCase


def create_synthetic_real_engineering_dataset() -> BenchmarkDataset:
    return BenchmarkDataset(
        "synthetic-real-engineering",
        (
            BenchmarkCase(
                id="real-engineering-esp32-s3-datasheet",
                name="ESP32-S3 text-layer Datasheet analysis",
                category="hardware",
                input="Analyze the supplied ESP32-S3 Datasheet engineering evidence.",
                expected={
                    "component_keywords": ["Power"],
                    "interfaces": ["SPI", "I2C", "UART", "USB"],
                    "constraint_keywords": ["voltage"],
                },
                metadata={
                    "fixture_kind": "synthetic_real_engineering",
                    "fixture_profile": "esp32_s3_text_layer_pdf",
                },
            ),
            BenchmarkCase(
                id="real-engineering-esp32-firmware-review",
                name="ESP32 deterministic Firmware review",
                category="firmware",
                input="Review the supplied ESP32 FreeRTOS Firmware sources.",
                expected={
                    "platform": "ESP32",
                    "components": [],
                    "templates": ["main.c"],
                },
                metadata={
                    "fixture_kind": "synthetic_real_engineering",
                    "fixture_profile": "esp32_freertos_sources",
                    "expected_rule": "freertos-task-starvation",
                },
            ),
            BenchmarkCase(
                id="real-engineering-datasheet-firmware-crosscheck",
                name="Datasheet and Firmware GPIO cross-check",
                category="end_to_end",
                input="Cross-check ESP32-S3 Datasheet pins against Firmware GPIO use.",
                expected={
                    "agents": ["FirmwareAgent", "HardwareAgent"],
                    "capabilities": ["firmware", "hardware"],
                },
                metadata={
                    "fixture_kind": "synthetic_real_engineering",
                    "fixture_profile": "esp32_gpio_conflict",
                    "expected_severity": "high",
                },
            ),
        ),
    )
