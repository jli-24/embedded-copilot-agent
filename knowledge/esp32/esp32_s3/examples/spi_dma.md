# ESP32-S3 SPI DMA example checklist

An SPI DMA example should make buffer ownership and completion explicit. Keep
buffers valid while a transfer is active, check every returned status, and avoid
sharing a transaction object between tasks without synchronization.

Clock, pins, host, queue depth, and DMA constraints remain project-specific and
must be verified with the selected ESP-IDF release and hardware design.
