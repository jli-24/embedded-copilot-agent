from __future__ import annotations

import math
from collections.abc import Sequence

from embedded_copilot.benchmark.exceptions import BenchmarkEvaluationError


def _normalized(value: object) -> object:
    return value.strip().casefold() if isinstance(value, str) else value


def _strings(values: Sequence[str]) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise BenchmarkEvaluationError("metric values must be a sequence of strings")
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise BenchmarkEvaluationError("metric values must be non-empty strings")
        candidate = value.strip().casefold()
        if candidate not in seen:
            seen.add(candidate)
            result.append(candidate)
    return result


class AccuracyMetric:
    @staticmethod
    def compute(expected: object, actual: object) -> float:
        return float(_normalized(expected) == _normalized(actual))


class CoverageMetric:
    @staticmethod
    def compute(
        expected: Sequence[str],
        actual: Sequence[str],
        *,
        substring: bool = True,
    ) -> float:
        required = _strings(expected)
        observed = _strings(actual)
        if not required:
            return 1.0
        if substring:
            matches = sum(
                any(requirement in candidate for candidate in observed)
                for requirement in required
            )
        else:
            observed_set = set(observed)
            matches = sum(requirement in observed_set for requirement in required)
        return matches / len(required)


class CapabilityCoverageMetric:
    _AGENTS = {
        "firmware": "firmwareagent",
        "hardware": "hardwareagent",
        "pcb": "pcbagent",
        "debug": "debugagent",
    }

    @classmethod
    def compute(
        cls,
        required: Sequence[str],
        actual: Sequence[str],
    ) -> float:
        capabilities = _strings(required)
        agents = set(_strings(actual))
        if not capabilities:
            raise BenchmarkEvaluationError(
                "at least one required capability is required"
            )
        if any(capability not in cls._AGENTS for capability in capabilities):
            raise BenchmarkEvaluationError("required capability is unsupported")
        matched = sum(cls._AGENTS[capability] in agents for capability in capabilities)
        return matched / len(capabilities)


class PassRateMetric:
    @staticmethod
    def compute(passed: int, total: int) -> float:
        if (
            isinstance(passed, bool)
            or isinstance(total, bool)
            or not isinstance(passed, int)
            or not isinstance(total, int)
            or total <= 0
            or passed < 0
            or passed > total
        ):
            raise BenchmarkEvaluationError("pass rate counts are invalid")
        return passed / total


class ScoreAggregator:
    @staticmethod
    def aggregate(scores: Sequence[float]) -> float:
        if not scores:
            raise BenchmarkEvaluationError("at least one score is required")
        normalized: list[float] = []
        for score in scores:
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                raise BenchmarkEvaluationError("scores must be numbers")
            candidate = float(score)
            if not math.isfinite(candidate) or not 0 <= candidate <= 1:
                raise BenchmarkEvaluationError("scores must be between zero and one")
            normalized.append(candidate)
        return sum(normalized) / len(normalized)
