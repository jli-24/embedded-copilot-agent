# STM32 HAL SPI guidance

STM32 HAL SPI code should track handle state, initialization results, transfer
timeouts, callbacks, DMA completion, and peripheral errors. The exact HAL API and
clock or GPIO setup depend on the selected STM32Cube package and MCU part.

Do not reuse a buffer or handle concurrently unless ownership and synchronization
are explicit.
