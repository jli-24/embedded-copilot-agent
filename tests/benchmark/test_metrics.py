import math

import pytest

from embedded_copilot.benchmark.metrics import (
    AccuracyMetric,
    CapabilityCoverageMetric,
    CoverageMetric,
    PassRateMetric,
    ScoreAggregator,
)
from embedded_copilot.benchmark.exceptions import BenchmarkEvaluationError


def test_accuracy_metric_compares_normalized_values() -> None:
    assert AccuracyMetric.compute(" ESP32 ", "esp32") == 1.0
    assert AccuracyMetric.compute("ESP32", "STM32") == 0.0


def test_coverage_metric_supports_exact_and_substring_matching() -> None:
    assert CoverageMetric.compute(["SPI", "GPIO"], ["gpio", "SPI"]) == 1.0
    assert CoverageMetric.compute(["camera", "wifi"], ["Camera module"]) == 0.5
    assert CoverageMetric.compute(
        ["camera", "wifi"],
        ["Camera module", "WiFi-capable MCU"],
        substring=True,
    ) == 1.0
    assert CoverageMetric.compute([], []) == 1.0


def test_pass_rate_and_score_aggregator_are_deterministic() -> None:
    assert PassRateMetric.compute(3, 4) == 0.75
    assert ScoreAggregator.aggregate([1.0, 0.5, 0.0]) == 0.5


def test_capability_coverage_maps_required_capabilities_to_agents() -> None:
    assert CapabilityCoverageMetric.compute(
        [" firmware ", "hardware", "PCB", "debug"],
        ["FirmwareAgent", "HardwareAgent", "PCBAgent"],
    ) == 0.75
    assert CapabilityCoverageMetric.compute(
        ["firmware", "FIRMWARE"],
        ["firmwareagent"],
    ) == 1.0


@pytest.mark.parametrize("required", [[], ["knowledge"]])
def test_capability_coverage_rejects_empty_or_unknown_requirements(
    required: list[str],
) -> None:
    with pytest.raises(BenchmarkEvaluationError):
        CapabilityCoverageMetric.compute(required, ["FirmwareAgent"])


@pytest.mark.parametrize(
    "call",
    [
        lambda: PassRateMetric.compute(-1, 2),
        lambda: PassRateMetric.compute(3, 2),
        lambda: PassRateMetric.compute(0, 0),
        lambda: ScoreAggregator.aggregate([]),
        lambda: ScoreAggregator.aggregate([math.nan]),
        lambda: ScoreAggregator.aggregate([1.1]),
    ],
)
def test_metrics_reject_invalid_inputs(call) -> None:
    with pytest.raises(BenchmarkEvaluationError):
        call()
