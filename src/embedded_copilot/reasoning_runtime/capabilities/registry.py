from __future__ import annotations

from embedded_copilot.reasoning_runtime.contracts import CapabilityEntry

CAPABILITIES: tuple[CapabilityEntry, ...] = (
    CapabilityEntry(name="context_analysis", version="1.0"),
    CapabilityEntry(name="risk_detection", version="1.0"),
    CapabilityEntry(name="verification_planning", version="1.0"),
)


def active_capabilities() -> tuple[CapabilityEntry, ...]:
    return CAPABILITIES
