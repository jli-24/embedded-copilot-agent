import pytest

from embedded_copilot.debug.analyzer import DebugRequirementAnalyzer
from embedded_copilot.debug.exceptions import DebugAnalysisError


@pytest.mark.parametrize(
    ("source", "platform"),
    [
        ("ESP32 panic reset", "ESP32"),
        ("ESP-IDF Guru Meditation", "ESP32"),
        ("STM32 HardFault", "STM32"),
        ("STM32 HAL timeout exception", "STM32"),
        ("FreeRTOS stack overflow", None),
    ],
)
def test_requirement_analyzer_normalizes_platform_context(
    source: str,
    platform: str | None,
) -> None:
    request = DebugRequirementAnalyzer().analyze(source)

    assert request.platform == platform


@pytest.mark.parametrize(
    ("source", "error_type"),
    [
        ("error: undefined reference to app_main", "compile_error"),
        ("Guru Meditation exception and reboot", "runtime_crash"),
        ("FreeRTOS stack overflow malloc failed", "memory_error"),
        ("STM32 UsageFault in handler", "hard_fault"),
        ("UART framing overrun", "communication_error"),
        ("I2C NACK bus error", "communication_error"),
        ("WiFi disconnect", "communication_error"),
        ("编译失败", "compile_error"),
        ("系统崩溃并重启", "runtime_crash"),
        ("内存不足", "memory_error"),
    ],
)
def test_requirement_analyzer_classifies_supported_errors(
    source: str,
    error_type: str,
) -> None:
    assert DebugRequirementAnalyzer().analyze(source).error_type == error_type


def test_requirement_analyzer_uses_fixed_error_precedence() -> None:
    request = DebugRequirementAnalyzer().analyze(
        "HardFault stack overflow error: UART reset"
    )

    assert request.error_type == "hard_fault"


def test_requirement_analyzer_applies_safe_metadata_overrides_and_copies() -> None:
    metadata = {
        "project_name": "  controlled  ",
        "platform": "esp-idf",
        "error_type": "COMPILE ERROR",
        "logs": [" error: one ", "ERROR: ONE", " undefined reference "],
        "nested": {"values": ["keep"]},
    }

    request = DebugRequirementAnalyzer().analyze("reboot", metadata=metadata)
    metadata["nested"]["values"].append("mutated")  # type: ignore[index,union-attr]

    assert request.project_name == "controlled"
    assert request.platform == "ESP32"
    assert request.error_type == "compile_error"
    assert request.logs == ["error: one", "undefined reference"]
    assert request.metadata == {"nested": {"values": ["keep"]}}


def test_requirement_analyzer_derives_logs_from_nonempty_source_lines() -> None:
    request = DebugRequirementAnalyzer().analyze(
        "error: first\n\n ERROR: FIRST \nundefined reference"
    )

    assert request.logs == ["error: first", "undefined reference"]


def test_requirement_analyzer_detects_from_explicit_logs_override() -> None:
    request = DebugRequirementAnalyzer().analyze(
        "please inspect this diagnostic",
        metadata={"logs": ["ESP32 Guru Meditation exception"]},
    )

    assert request.platform == "ESP32"
    assert request.error_type == "runtime_crash"
    assert request.logs == ["ESP32 Guru Meditation exception"]


def test_requirement_analyzer_rejects_unknown_request() -> None:
    with pytest.raises(DebugAnalysisError, match="could not classify"):
        DebugRequirementAnalyzer().analyze("device behavior is unclear")


@pytest.mark.parametrize(
    "source",
    [
        "ESP32 SPI configuration is valid",
        "STM32 UART is configured",
        "I2C peripheral initialization",
    ],
)
def test_requirement_analyzer_does_not_infer_failure_from_interface_name(
    source: str,
) -> None:
    with pytest.raises(DebugAnalysisError, match="could not classify"):
        DebugRequirementAnalyzer().analyze(source)


def test_uart_error_colon_is_not_misclassified_as_compile_error() -> None:
    request = DebugRequirementAnalyzer().analyze(
        "UART framing error: overrun"
    )

    assert request.error_type == "communication_error"


@pytest.mark.parametrize(
    "metadata",
    [
        {"project_name": " "},
        {"project_name": None},
        {"platform": "Linux"},
        {"platform": "HAL"},
        {"platform": None},
        {"error_type": "mystery"},
        {"error_type": None},
        {"logs": "not-a-list"},
        {"logs": None},
        {"logs": []},
        {"logs": [""]},
    ],
)
def test_requirement_analyzer_rejects_invalid_overrides(metadata: object) -> None:
    with pytest.raises(DebugAnalysisError):
        DebugRequirementAnalyzer().analyze("error: compile failed", metadata=metadata)
