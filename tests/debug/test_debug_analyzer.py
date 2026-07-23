from __future__ import annotations

import pytest

from embedded_copilot.debug.analyzer import DebugAnalyzer
from embedded_copilot.debug.models import DebugEvidence, DebugRequest


@pytest.mark.parametrize(
    ("error_type", "log", "finding_id"),
    [
        ("compile_error", "fatal error: driver.h: No such file", "compile_missing_include"),
        ("compile_error", "undefined reference to app_main", "compile_missing_symbol"),
        ("compile_error", "conflicting types for callback", "compile_type_mismatch"),
        ("runtime_crash", "task watchdog triggered", "runtime_watchdog"),
        ("runtime_crash", "software reset and reboot", "runtime_reset"),
        ("runtime_crash", "Guru Meditation exception", "runtime_exception"),
        ("memory_error", "FreeRTOS stack overflow", "memory_stack_overflow"),
        ("memory_error", "heap malloc failed", "memory_allocation_failure"),
        ("hard_fault", "HardFault address 0x00000000 null", "hardfault_null_access_candidate"),
        ("hard_fault", "BusFault invalid memory access", "hardfault_memory_access"),
        ("hard_fault", "HardFault occurred in ISR handler", "hardfault_interrupt_context"),
        ("communication_error", "UART framing error overrun", "communication_uart_error"),
        ("communication_error", "SPI transaction timeout", "communication_spi_error"),
        ("communication_error", "I2C NACK bus error", "communication_i2c_error"),
        ("communication_error", "WiFi disconnect reason", "communication_wifi_disconnect"),
    ],
)
def test_debug_analyzer_emits_stable_rule_findings(
    error_type: str,
    log: str,
    finding_id: str,
) -> None:
    request = DebugRequest(
        input=log,
        error_type=error_type,  # type: ignore[arg-type]
        logs=[log],
    )

    findings = DebugAnalyzer().analyze(request, [])

    assert finding_id in [finding.id for finding in findings]
    assert all(
        "observed" in finding.description.casefold()
        or "candidate" in finding.description.casefold()
        for finding in findings
    )


@pytest.mark.parametrize(
    ("error_type", "log", "generic_id"),
    [
        ("compile_error", "compilation failed", "compile_error_observed"),
        ("runtime_crash", "application crash", "runtime_crash_observed"),
        ("hard_fault", "HardFault", "hardfault_observed"),
        ("communication_error", "communication failure", "communication_error_observed"),
    ],
)
def test_debug_analyzer_emits_generic_fallback(
    error_type: str,
    log: str,
    generic_id: str,
) -> None:
    request = DebugRequest(
        input=log,
        error_type=error_type,  # type: ignore[arg-type]
        logs=[log],
    )

    assert [item.id for item in DebugAnalyzer().analyze(request, [])] == [generic_id]


def test_debug_analyzer_bounds_evidence_lines_and_length() -> None:
    long_line = "watchdog " + ("x" * 800)
    request = DebugRequest(
        input="watchdog",
        error_type="runtime_crash",
        logs=[long_line, "watchdog two", "watchdog three", "watchdog four"],
    )

    finding = DebugAnalyzer().analyze(request, [])[0]

    assert len(finding.evidence) == 3
    assert all(len(line) <= 500 for line in finding.evidence)


def test_knowledge_evidence_enriches_metadata_but_cannot_create_finding() -> None:
    request = DebugRequest(
        input="compilation failed",
        error_type="compile_error",
        logs=["compilation failed"],
    )
    evidence = DebugEvidence(
        source="LOCAL:symbol-doc",
        category="compile",
        content="undefined reference private document body",
    )

    findings = DebugAnalyzer().analyze(request, [evidence])

    assert [finding.id for finding in findings] == ["compile_error_observed"]
    assert findings[0].metadata["knowledge_sources"] == ["LOCAL:symbol-doc"]
    assert "private document body" not in str(findings[0].model_dump(mode="json"))


@pytest.mark.parametrize(
    ("error_type", "log"),
    [
        ("compile_error", "build configuration is valid"),
        ("runtime_crash", "application is running"),
        ("hard_fault", "fault handler is configured"),
        ("communication_error", "SPI configuration is valid"),
    ],
)
def test_debug_analyzer_requires_observed_signature_for_generic_finding(
    error_type: str,
    log: str,
) -> None:
    request = DebugRequest(
        input=log,
        error_type=error_type,  # type: ignore[arg-type]
        logs=[log],
    )

    assert DebugAnalyzer().analyze(request, []) == []
