from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence

from pydantic import ValidationError

from embedded_copilot.debug.exceptions import DebugAnalysisError
from embedded_copilot.debug.models import DebugEvidence, DebugFinding, DebugRequest


_PLATFORM_ALIASES = {
    "esp32": "ESP32",
    "esp-idf": "ESP32",
    "esp idf": "ESP32",
    "stm32": "STM32",
    "stm32 hal": "STM32",
}
_ERROR_TYPE_ALIASES = {
    "compile": "compile_error",
    "compile error": "compile_error",
    "compile_error": "compile_error",
    "runtime": "runtime_crash",
    "runtime crash": "runtime_crash",
    "runtime_crash": "runtime_crash",
    "crash": "runtime_crash",
    "memory": "memory_error",
    "memory error": "memory_error",
    "memory_error": "memory_error",
    "hardfault": "hard_fault",
    "hard fault": "hard_fault",
    "hard_fault": "hard_fault",
    "communication": "communication_error",
    "communication error": "communication_error",
    "communication_error": "communication_error",
}
_ERROR_MARKERS = (
    (
        "hard_fault",
        ("hardfault", "hard fault", "usagefault", "busfault", "memmanage"),
    ),
    (
        "memory_error",
        (
            "stack overflow",
            "heap",
            "malloc failed",
            "allocation failed",
            "out of memory",
            "内存不足",
        ),
    ),
    (
        "compile_error",
        (
            "undefined reference",
            "compilation failed",
            "compile failed",
            "compiler error",
            "no such file",
            "file not found",
            "conflicting types",
            "incompatible type",
            "type mismatch",
            "编译失败",
        ),
    ),
    (
        "communication_error",
        (
            "wi-fi disconnect",
            "wifi disconnect",
            "communication failure",
            "communication error",
        ),
    ),
    (
        "runtime_crash",
        (
            "guru meditation",
            "crash",
            "exception",
            "reboot",
            "reset",
            "watchdog",
            "esp_error_check failed",
            "hal_error",
            "hal_timeout",
            "崩溃",
            "重启",
        ),
    ),
)
_CONTROL_FIELDS = {"project_name", "platform", "error_type", "logs"}


class DebugRequirementAnalyzer:
    """Normalize debug input with deterministic embedded-domain rules."""

    def analyze(
        self,
        source: str,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> DebugRequest:
        try:
            if not isinstance(source, str) or not source.strip():
                raise ValueError("debug source must not be empty")
            if metadata is not None and not isinstance(metadata, Mapping):
                raise TypeError("metadata must be a mapping")
            copied = copy.deepcopy(dict(metadata or {}))
            project_name_supplied = "project_name" in copied
            platform_supplied = "platform" in copied
            error_type_supplied = "error_type" in copied
            logs_supplied = "logs" in copied
            project_name = copied.pop("project_name", None)
            platform_override = copied.pop("platform", None)
            error_override = copied.pop("error_type", None)
            logs_override = copied.pop("logs", None)
            if project_name_supplied and (
                not isinstance(project_name, str) or not project_name.strip()
            ):
                raise ValueError("project_name override is invalid")
            if logs_supplied and (
                not isinstance(logs_override, list) or not logs_override
            ):
                raise ValueError("logs override is invalid")
            if logs_supplied and any(
                not isinstance(line, str) or not line.strip()
                for line in logs_override
            ):
                raise ValueError("logs override is invalid")
            diagnostic_source = "\n".join(
                [source, *(logs_override if logs_supplied else [])]
            )
            platform = (
                self._normalize_platform(platform_override)
                if platform_supplied
                else self._detect_platform(diagnostic_source)
            )
            error_type = (
                self._normalize_error_type(error_override)
                if error_type_supplied
                else self._detect_error_type(diagnostic_source)
            )
            if error_type is None:
                raise DebugAnalysisError("debug error type could not classify")
            logs = (
                logs_override
                if logs_supplied
                else [line for line in source.splitlines() if line.strip()]
            )
            return DebugRequest(
                input=source,
                project_name=project_name,
                platform=platform,
                error_type=error_type,
                logs=logs,
                metadata={
                    key: value
                    for key, value in copied.items()
                    if key not in _CONTROL_FIELDS
                },
            )
        except DebugAnalysisError:
            raise
        except (TypeError, ValueError, ValidationError) as exc:
            raise DebugAnalysisError("debug requirement analysis failed") from exc

    @staticmethod
    def _detect_platform(source: str) -> str | None:
        normalized = source.casefold()
        if "esp32" in normalized or "esp-idf" in normalized:
            return "ESP32"
        if "stm32" in normalized or "stm32 hal" in normalized:
            return "STM32"
        return None

    @staticmethod
    def _normalize_platform(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("platform override is invalid")
        canonical = _PLATFORM_ALIASES.get(value.strip().casefold())
        if canonical is None:
            raise ValueError("platform override is unknown")
        return canonical

    @staticmethod
    def _detect_error_type(source: str) -> str | None:
        normalized = source.casefold()
        for error_type, markers in _ERROR_MARKERS:
            if error_type == "communication_error":
                if _has_communication_failure(normalized):
                    return error_type
                continue
            if any(marker in normalized for marker in markers):
                return error_type
        return None

    @staticmethod
    def _normalize_error_type(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("error_type override is invalid")
        normalized = " ".join(value.strip().casefold().replace("-", " ").split())
        canonical = _ERROR_TYPE_ALIASES.get(normalized)
        if canonical is None:
            canonical = _ERROR_TYPE_ALIASES.get(value.strip().casefold())
        if canonical is None:
            raise ValueError("error_type override is unknown")
        return canonical


_FINDING_RULES: dict[str, tuple[tuple[str, tuple[str, ...], str, str, str], ...]] = {
    "compile_error": (
        ("compile_missing_include", ("no such file", "file not found"), "error", "Observed a missing include signature.", "Verify the include path and dependency availability, then rebuild."),
        ("compile_missing_symbol", ("undefined reference", "undeclared", "not declared"), "error", "Observed a missing symbol signature.", "Locate the first missing symbol and verify its declaration, definition, and link inputs."),
        ("compile_type_mismatch", ("conflicting types", "incompatible type", "type mismatch"), "error", "Observed a type mismatch signature.", "Compare the declaration and use-site types, then rebuild with full warnings enabled."),
    ),
    "runtime_crash": (
        ("runtime_watchdog", ("watchdog",), "critical", "Observed a watchdog-related runtime signature; the blocking cause remains a candidate.", "Inspect task scheduling, blocking calls, and watchdog feed timing before reproducing."),
        ("runtime_reset", ("reset", "reboot"), "error", "Observed a reset or reboot signature.", "Capture the reset reason and the events immediately before restart, then reproduce."),
        ("runtime_exception", ("guru meditation", "exception", "esp_error_check failed", "abort"), "critical", "Observed an exception or abort signature.", "Symbolize the captured stack or program counter and inspect the first application frame."),
    ),
    "memory_error": (
        ("memory_stack_overflow", ("stack overflow",), "critical", "Observed a stack overflow signature.", "Measure task stack high-water marks and inspect large local allocations before resizing."),
        ("memory_allocation_failure", ("heap", "malloc", "allocation failed", "out of memory"), "critical", "Observed a memory allocation failure signature.", "Record free heap and allocation sizes over time, then check ownership and fragmentation."),
    ),
    "hard_fault": (
        ("hardfault_null_access_candidate", ("0x00000000", "null"), "critical", "Observed a null-address marker; null access is a candidate cause.", "Symbolize the fault location and validate pointers used by the faulting instruction."),
        ("hardfault_memory_access", ("busfault", "memmanage", "invalid memory access"), "critical", "Observed a memory-access fault signature.", "Decode the captured fault status and address registers, then inspect the faulting instruction."),
        ("hardfault_interrupt_context", ("isr", "interrupt"), "critical", "Observed an interrupt-context marker; interrupt misuse is a candidate cause.", "Inspect the active exception and verify interrupt-safe API and stack usage."),
    ),
    "communication_error": (
        ("communication_uart_error", ("uart", "framing error", "overrun"), "error", "Observed a UART framing or overrun signature.", "Verify UART configuration and capture framing, overrun, and timing evidence at both endpoints."),
        ("communication_spi_error", ("spi",), "error", "Observed an SPI transaction failure signature.", "Verify SPI mode, clock, chip-select timing, and transaction return status."),
        ("communication_i2c_error", ("i2c", "nack", "bus error"), "error", "Observed an I2C NACK or bus-error signature.", "Check device address, pull-ups, bus timing, and capture the first failing transaction."),
        ("communication_wifi_disconnect", ("wifi disconnect", "wi-fi disconnect"), "warning", "Observed a WiFi disconnect signature.", "Record disconnect reason codes and correlate them with signal and access-point events."),
    ),
}

_GENERIC_FINDINGS = {
    "compile_error": ("compile_error_observed", "Observed a generic compiler failure signature.", "Inspect the first compiler diagnostic and fix errors in source order before rebuilding."),
    "runtime_crash": ("runtime_crash_observed", "Observed a generic runtime crash signature.", "Capture the earliest crash output and symbolize available addresses before reproducing."),
    "hard_fault": ("hardfault_observed", "Observed a generic HardFault signature.", "Capture fault registers, stack frame, ELF, map file, and the exact reproduction conditions."),
    "communication_error": ("communication_error_observed", "Observed a generic communication failure signature.", "Capture both endpoints, configuration, timing, and the first failing transaction."),
}

_GENERIC_MARKERS = {
    "compile_error": ("compilation failed", "compile failed", "compiler error"),
    "runtime_crash": ("crash", "runtime failure"),
    "hard_fault": ("hardfault", "hard fault"),
    "communication_error": ("communication failure", "communication error"),
}


class DebugAnalyzer:
    """Produce deterministic findings from observed input signatures only."""

    def analyze(
        self,
        request: DebugRequest,
        evidence: Sequence[DebugEvidence],
    ) -> list[DebugFinding]:
        logs = request.logs or [request.input]
        knowledge_sources = _stable_sources(evidence)
        findings: list[DebugFinding] = []
        for finding_id, markers, severity, description, recommendation in _FINDING_RULES.get(request.error_type, ()):
            matching = [
                line[:500]
                for line in logs
                if _matches_finding_rule(finding_id, line, markers)
            ][:3]
            if matching:
                findings.append(
                    DebugFinding(
                        id=finding_id,
                        category=request.error_type,
                        severity=severity,
                        description=description,
                        evidence=matching,
                        recommendation=recommendation,
                        metadata={"knowledge_sources": knowledge_sources},
                    )
                )
        generic_markers = _GENERIC_MARKERS.get(request.error_type, ())
        generic_evidence = [
            line[:500]
            for line in logs
            if any(marker in line.casefold() for marker in generic_markers)
        ][:3]
        if (
            not findings
            and generic_evidence
            and request.error_type in _GENERIC_FINDINGS
        ):
            finding_id, description, recommendation = _GENERIC_FINDINGS[request.error_type]
            findings.append(
                DebugFinding(
                    id=finding_id,
                    category=request.error_type,
                    severity="error",
                    description=description,
                    evidence=generic_evidence,
                    recommendation=recommendation,
                    metadata={"knowledge_sources": knowledge_sources},
                )
            )
        return findings


def _stable_sources(evidence: Sequence[DebugEvidence]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in evidence:
        key = item.source.casefold()
        if key not in seen:
            seen.add(key)
            result.append(item.source)
    return result


def _has_communication_failure(value: str) -> bool:
    if "wifi disconnect" in value or "wi-fi disconnect" in value:
        return True
    if "uart" in value and any(
        marker in value for marker in ("framing error", "overrun")
    ):
        return True
    if "spi" in value and any(
        marker in value for marker in ("failure", "failed", "error", "timeout")
    ):
        return True
    if "i2c" in value and any(
        marker in value
        for marker in ("nack", "bus error", "failure", "failed", "timeout")
    ):
        return True
    return "communication failure" in value or "communication error" in value


def _matches_finding_rule(
    finding_id: str,
    line: str,
    markers: tuple[str, ...],
) -> bool:
    normalized = line.casefold()
    if finding_id == "communication_uart_error":
        return "uart" in normalized and any(
            marker in normalized for marker in ("framing error", "overrun")
        )
    if finding_id == "communication_spi_error":
        return "spi" in normalized and any(
            marker in normalized
            for marker in ("failure", "failed", "error", "timeout")
        )
    if finding_id == "communication_i2c_error":
        return "i2c" in normalized and any(
            marker in normalized
            for marker in ("nack", "bus error", "failure", "failed", "timeout")
        )
    return any(marker in normalized for marker in markers)
