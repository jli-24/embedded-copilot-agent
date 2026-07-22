# FreeRTOS task guidance

Task design should state scheduler state, priority, stack budget, blocking
timeouts, and ownership of queues, semaphores, mutexes, and shared buffers.
Blocking APIs do not belong in an ISR; use the documented FromISR variant only
when execution is actually in interrupt context.

Avoid busy-waiting and account for priority inversion when choosing synchronization.
