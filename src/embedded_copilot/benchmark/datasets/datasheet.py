from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from embedded_copilot.benchmark.dataset import BenchmarkDataset
from embedded_copilot.benchmark.models import BenchmarkCase


@dataclass(frozen=True, slots=True)
class SyntheticDatasheetFixture:
    filename: str
    content: str


_ESP32_S3 = """# ESP32-S3 Datasheet

Manufacturer: Espressif
Part Number: ESP32-S3
Category: MCU
Package: QFN-56
Description: Wi-Fi and Bluetooth MCU

## Pins

| Pin Number | Pin Name | Type | Description |
| --- | --- | --- | --- |
| 43 | U0TXD | output | UART transmit |
| 44 | U0RXD | input | UART receive |

## Interfaces

| Name | Protocol | Pins |
| --- | --- | --- |
| UART0 | UART | 43, 44 |

## Electrical Specs

| Parameter | Min | Typical | Max | Unit |
| --- | --- | --- | --- | --- |
| Supply voltage | 3.0 | 3.3 | 3.6 | V |
"""

_STM32 = """STM32F407VG Datasheet
Manufacturer: STMicroelectronics
Part Number: STM32F407VG
Category: MCU
Package: LQFP-100
Description: Arm Cortex-M4 microcontroller
Pin: 42 | PA9 | alternate | USART1 transmit
Pin: 43 | PA10 | alternate | USART1 receive
Interface: USART1 | UART | 42, 43
Voltage: Supply voltage | 1.8 | 3.3 | 3.6 | V
"""

_POWER_CONSTRAINT = """# TPS62162 Datasheet

Manufacturer: Texas Instruments
Part Number: TPS62162
Category: Power regulator
Package: QFN-8
Description: Step-down power converter

## Electrical Specs

| Parameter | Min | Typical | Max | Unit |
| --- | --- | --- | --- | --- |
| Supply voltage | 3.0 | 5.0 | 17.0 | V |
| Output current | - | 0.5 | 1.0 | A |
"""


SYNTHETIC_DATASHEET_FIXTURES = MappingProxyType(
    {
        "esp32-s3": SyntheticDatasheetFixture(
            filename="esp32-s3.md",
            content=_ESP32_S3,
        ),
        "stm32": SyntheticDatasheetFixture(
            filename="stm32.pdf",
            content=_STM32,
        ),
        "power-constraint": SyntheticDatasheetFixture(
            filename="power-constraint.md",
            content=_POWER_CONSTRAINT,
        ),
    }
)


def create_synthetic_datasheet_intelligence_dataset() -> BenchmarkDataset:
    return BenchmarkDataset(
        "synthetic-datasheet-intelligence",
        [
            BenchmarkCase(
                id="synthetic-datasheet-esp32-s3",
                name="Synthetic ESP32-S3 Datasheet evidence",
                category="hardware",
                input="Design ESP32-S3 UART hardware using structured evidence.",
                expected={
                    "component_keywords": ["UART"],
                    "interfaces": ["UART"],
                    "constraint_keywords": ["voltage"],
                },
                metadata={
                    "fixture_kind": "synthetic",
                    "datasheet_fixture_id": "esp32-s3",
                },
            ),
            BenchmarkCase(
                id="synthetic-datasheet-stm32",
                name="Synthetic STM32 Datasheet evidence",
                category="firmware",
                input="Create STM32 HAL UART firmware using structured evidence.",
                expected={
                    "platform": "STM32",
                    "components": ["uart", "UART"],
                    "templates": ["Core/Src/main.c", "Core/Src/uart.c"],
                },
                metadata={
                    "fixture_kind": "synthetic",
                    "datasheet_fixture_id": "stm32",
                },
            ),
            BenchmarkCase(
                id="synthetic-datasheet-power-constraint",
                name="Synthetic power Datasheet constraint evidence",
                category="pcb",
                input="Review TPS62162 power PCB constraints using structured evidence.",
                expected={
                    "rules": [
                        "pcb-power-declaration",
                        "pcb-power-decoupling",
                        "pcb-ground-integrity",
                    ],
                    "issue_ids": [
                        "pcb-power-decoupling",
                        "pcb-ground-integrity",
                    ],
                    "severities": {
                        "pcb-power-decoupling": "warning",
                        "pcb-ground-integrity": "warning",
                    },
                },
                metadata={
                    "fixture_kind": "synthetic",
                    "datasheet_fixture_id": "power-constraint",
                    "project_name": "TPS62162",
                },
            ),
        ],
    )
