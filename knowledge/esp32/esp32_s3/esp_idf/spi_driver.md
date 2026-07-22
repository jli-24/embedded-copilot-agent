# ESP-IDF SPI driver guidance

Prefer the supported ESP-IDF SPI driver for the configured target and SDK
version. Define bus ownership, device configuration, transaction lifetime,
timeouts, return-code handling, and the task or ISR context that submits work.

DMA buffers require valid lifetime, size, alignment, and ownership until the
driver reports completion. This seed is general guidance, not an API reference.
