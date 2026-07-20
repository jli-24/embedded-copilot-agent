---
name: embedded-c-knowledge
description: Apply Embedded Copilot embedded-domain constraints when reasoning about firmware, code, debugging, retrieval content, or tools involving C, ESP32, STM32, ESP-IDF, STM32 HAL, UART, SPI, I2C, or FreeRTOS.
---

# Embedded C Knowledge

Use this Skill as a first-stage knowledge constraint. Do not assume access to hardware, datasheets, register maps, SDK versions, or measured signals unless provided or retrieved with a citation.

## Reasoning Workflow

1. Identify target MCU, board, SDK or HAL version, clocking, pins, and peripheral instance.
2. Separate facts from assumptions and list missing hardware context.
3. Prefer vendor-supported APIs before direct register access unless the task requires registers.
4. Check ownership, lifetime, concurrency, interrupt context, timing, and error paths.
5. Tie recommendations to cited documentation or clearly label them as general guidance.
6. For debugging, request or inspect observable evidence before claiming root cause.

## Coverage

- C: types, integer width, volatile, memory lifetime, alignment, bit operations, undefined behavior, and error handling.
- ESP32 and ESP-IDF: components, drivers, tasks, queues, events, logging, and configuration awareness.
- STM32 and HAL: handles, initialization, callbacks, DMA, interrupts, clocks, and peripheral state.
- UART: framing, baud tolerance, buffering, flow control, interrupt or DMA behavior.
- SPI: mode, clock, chip select, word order, transaction ownership, and electrical limits.
- I2C: addressing, pull-ups, bus speed, ACK/NACK, repeated start, arbitration, and recovery.
- FreeRTOS basics: tasks, priorities, queues, semaphores, event groups, ISR-safe APIs, stack, and blocking.

Read [references/domain-constraints.md](references/domain-constraints.md) when producing firmware guidance, diagnostic hypotheses, or embedded test cases.

## Safety and Accuracy

- Never invent pin mappings, register values, interrupt names, or HAL signatures.
- Distinguish ISR-safe APIs from task-context APIs.
- Treat volatile as an access constraint, not a synchronization primitive.
- Check buffer bounds, ownership, and termination for all C strings and byte arrays.
- Mention hardware-dependent assumptions such as voltage levels, pull-ups, clocks, and grounding.
- Do not present unverified generated code as hardware-tested.
