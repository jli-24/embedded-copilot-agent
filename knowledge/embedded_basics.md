# Embedded Copilot v0.1 Original Knowledge Seed

This document is original project material for offline development and testing.
It is general engineering guidance, not a replacement for the applicable
vendor datasheet, reference manual, or SDK documentation.

## ESP32 SPI configuration

An ESP32 SPI design must identify the exact ESP32 family, ESP-IDF version,
controller role, SPI host, clock frequency, SPI mode, bit order, word width,
chip-select behavior, and GPIO routing. Prefer the supported ESP-IDF SPI driver
for the selected SDK version. Do not copy a pin mapping without checking the
board schematic and the selected chip's GPIO restrictions.

Before a transfer, verify voltage compatibility, controller and peripheral
clock limits, transaction ownership, MOSI and MISO direction, SCLK behavior,
and chip-select timing. Return and inspect the SDK error status for
initialization and transfer operations.

## ESP32 FreeRTOS LED task

An LED task should receive the GPIO number and active level from configuration
instead of assuming a board pin. Configure the GPIO as an output before the
task starts. The task may toggle the output and call `vTaskDelay()` with
`pdMS_TO_TICKS()` so it does not busy-wait.

The design must state the ESP-IDF version, target board, GPIO ownership, task
priority, stack size, and whether another component accesses the same GPIO.
Generated code is an example until it is compiled for the selected target and
verified on real hardware.

## Debug evidence

For an ESP32 Guru Meditation Error, directly visible exception text, register
dump, Backtrace addresses, ELF file, map file, firmware build identifier, and
reproduction steps are evidence. A decoded source line is stronger evidence
than an undecoded address. A likely cause remains an inference until the
Backtrace and relevant source confirm it.

For an STM32 HardFault, capture the stacked registers, fault status registers,
stack pointer, firmware image, map file, and exact MCU. For compiler errors,
preserve the complete diagnostic, file, line, compiler version, and build
flags. Never convert a hypothesis into an observed fact.
