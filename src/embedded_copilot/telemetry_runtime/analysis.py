from __future__ import annotations

import math
from fractions import Fraction

from embedded_copilot.telemetry_runtime.models import (
    TelemetryAnalysisResult,
    TelemetryAnomalyCandidate,
    TelemetryAnomalyDirection,
    TelemetrySeriesSnapshot,
    TelemetryStatistics,
    TelemetryTrend,
)


def analyze_series(
    *,
    series: TelemetrySeriesSnapshot,
    lower_bound: int | float | None,
    upper_bound: int | float | None,
) -> TelemetryAnalysisResult:
    values = tuple(point.value for point in series.samples)
    minimum = min(values)
    maximum = max(values)
    average = _normalize_zero(_average(values))
    delta = _normalize_zero(_difference(values[-1], values[0]))
    if delta > 0:
        trend = TelemetryTrend.INCREASING
    elif delta < 0:
        trend = TelemetryTrend.DECREASING
    else:
        trend = TelemetryTrend.STABLE

    directions: list[TelemetryAnomalyDirection] = []
    if lower_bound is not None and minimum < lower_bound:
        directions.append(TelemetryAnomalyDirection.BELOW_LOWER_BOUND)
    if upper_bound is not None and maximum > upper_bound:
        directions.append(TelemetryAnomalyDirection.ABOVE_UPPER_BOUND)

    candidate = None
    if directions:
        candidate = TelemetryAnomalyCandidate(
            directions=tuple(directions),
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            observed_minimum=minimum,
            observed_maximum=maximum,
        )
    return TelemetryAnalysisResult(
        statistics=TelemetryStatistics(
            minimum=minimum,
            maximum=maximum,
            average=average,
            delta=delta,
            sample_count=len(values),
        ),
        trend=trend,
        anomaly_candidate=candidate,
    )


def _normalize_zero(value: int | float) -> int | float:
    return 0.0 if value == 0 else value


def _average(values: tuple[int | float, ...]) -> float:
    try:
        return math.fsum(values) / len(values)
    except OverflowError:
        scale = max(abs(value) for value in values)
        normalized = math.fsum(value / scale for value in values) / len(values)
        return 0.0 if normalized == 0 else scale * normalized


def _difference(last: int | float, first: int | float) -> int | float:
    delta = last - first
    if isinstance(delta, int) or math.isfinite(delta):
        return delta
    exact = Fraction(last) - Fraction(first)
    if exact.denominator == 1:
        return exact.numerator
    raise ArithmeticError
