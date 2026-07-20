# Embedded Domain Constraints

## C

- Use fixed-width integers for protocol and register data.
- Check signedness, promotion, overflow, alignment, aliasing, lifetime, and buffer length.
- Use volatile for externally changing objects; use atomics, critical sections, or RTOS primitives for synchronization.
- Keep ISR work bounded and avoid blocking or non-ISR-safe APIs.

## ESP32 and ESP-IDF

- Confirm chip family and ESP-IDF version before naming APIs or peripherals.
- Respect component boundaries, Kconfig settings, task context, driver ownership, and error codes.
- Prefer official drivers and esp_err_t handling.

## STM32 and HAL

- Confirm STM32 family, exact part, Cube or HAL version, clock tree, GPIO alternate functions, and handle state.
- Treat callbacks, interrupts, DMA completion, cache coherency, and peripheral errors as explicit state transitions.
- Do not infer register values or IRQ names without the device reference.

## UART

Verify baud, data bits, parity, stop bits, voltage standard, flow control, buffer capacity, framing or overrun errors, and interrupt or DMA ownership.

## SPI

Verify controller and peripheral roles, mode, clock limit, bit order, word width, chip-select timing, full-duplex expectations, voltage, and transaction boundaries.

## I2C

Verify 7-bit versus 10-bit address form, pull-up values, voltage, bus capacitance, speed, repeated-start needs, clock stretching, ACK or NACK handling, and bus recovery.

## FreeRTOS

- Confirm scheduler state, task priorities, stack sizes, blocking timeouts, and object ownership.
- Use FromISR variants only in interrupt context and propagate the yield request correctly.
- Avoid priority inversion; choose mutexes where priority inheritance is required.
- Do not call blocking APIs while holding a critical section or from an ISR.

## Evidence Labels

Label conclusions as one of:

- observed: directly present in logs, code, measurements, or tool output
- cited: supported by a retrieved authoritative source
- inferred: consistent with evidence but not yet confirmed
- assumed: required context is missing

Never upgrade an inferred or assumed claim to observed.
