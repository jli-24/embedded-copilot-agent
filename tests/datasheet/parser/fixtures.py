from __future__ import annotations


ESP32_MARKDOWN = """# ESP32-S3 Datasheet

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
| Active current | - | 25 | 50 | mA |
"""


STM32_PDF_TEXT = """STM32F407VG Datasheet
Manufacturer: STMicroelectronics
Part Number: STM32F407VG
Category: MCU
Package: LQFP-100
Description: Arm Cortex-M4 microcontroller
Pin: 42 | PA9 | alternate | USART1 transmit
Pin: 43 | PA10 | alternate | USART1 receive
Interface: USART1 | UART | 42, 43
Voltage: Supply voltage | 1.8 | 3.3 | 3.6 | V
Current: Run current | - | 30 | 80 | mA
"""
