from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from embedded_copilot.benchmark.models import (
    BenchmarkCase,
    BenchmarkReport,
    BenchmarkResult,
)


def _result(case_id: str = "case-1", *, success: bool = True) -> BenchmarkResult:
    return BenchmarkResult(
        case_id=case_id,
        success=success,
        score=1.0 if success else 0.5,
        metrics={"accuracy": 1.0 if success else 0.5},
        errors=[] if success else ["metric below required score: accuracy"],
        metadata={"category": "routing", "target_name": "SupervisorAgent"},
    )


def test_benchmark_case_strips_contract_strings_and_isolates_nested_values() -> None:
    expected = {"agents": ["FirmwareAgent"]}
    metadata = {"nested": {"keep": True}}

    case = BenchmarkCase(
        id=" route-1 ",
        name=" route case ",
        category=" routing ",
        input=" firmware request ",
        expected=expected,
        metadata=metadata,
    )
    expected["agents"].append("PCBAgent")  # type: ignore[union-attr]
    metadata["nested"]["keep"] = False  # type: ignore[index]

    assert case.id == "route-1"
    assert case.name == "route case"
    assert case.category == "routing"
    assert case.input == "firmware request"
    assert case.expected == {"agents": ["FirmwareAgent"]}
    assert case.metadata == {"nested": {"keep": True}}


def test_benchmark_models_are_frozen_and_forbid_extra_fields() -> None:
    case = BenchmarkCase(
        id="case",
        name="case",
        category="firmware",
        input="ESP32 firmware",
        expected={},
    )

    with pytest.raises(ValidationError):
        case.id = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        BenchmarkResult(
            case_id="case",
            success=True,
            score=1,
            extra=True,  # type: ignore[call-arg]
        )


@pytest.mark.parametrize("score", [-0.1, 1.1, math.inf, math.nan])
def test_benchmark_result_rejects_invalid_score(score: float) -> None:
    with pytest.raises(ValidationError):
        BenchmarkResult(case_id="case", success=True, score=score)


def test_benchmark_result_validates_metrics_and_outcome_invariant() -> None:
    assert _result().errors == []
    with pytest.raises(ValidationError):
        BenchmarkResult(
            case_id="case",
            success=True,
            score=1,
            errors=["unexpected"],
        )
    with pytest.raises(ValidationError):
        BenchmarkResult(case_id="case", success=False, score=0)
    with pytest.raises(ValidationError):
        BenchmarkResult(
            case_id="case",
            success=False,
            score=0,
            metrics={"bad": 1.1},
            errors=["bad"],
        )


def test_benchmark_result_stably_deduplicates_errors() -> None:
    result = BenchmarkResult(
        case_id="case",
        success=False,
        score=0,
        errors=[" Failed ", "failed", " Other "],
    )

    assert result.errors == ["Failed", "Other"]


def test_benchmark_result_normalizes_tuple_string_lists() -> None:
    result = BenchmarkResult(
        case_id="case",
        success=False,
        score=0,
        errors=(" Failed ", "failed", " Other "),  # type: ignore[arg-type]
    )

    assert result.errors == ["Failed", "Other"]


def test_benchmark_result_and_report_reject_unsafe_metadata_keys() -> None:
    with pytest.raises(ValidationError):
        BenchmarkResult(
            case_id="case",
            success=True,
            score=1,
            metadata={"raw_output": "PRIVATE_SENTINEL"},
        )

    with pytest.raises(ValidationError):
        BenchmarkReport(
            name="suite",
            total_cases=1,
            passed_cases=1,
            failed_cases=0,
            average_score=1,
            results=[_result()],
            summary="summary",
            metadata={"trace": "PRIVATE_SENTINEL"},
        )


def test_benchmark_report_validates_counts_ids_and_average() -> None:
    report = BenchmarkReport(
        name=" suite ",
        total_cases=2,
        passed_cases=1,
        failed_cases=1,
        average_score=0.75,
        metrics={"pass_rate": 0.5},
        results=[_result("one"), _result("two", success=False)],
        summary=" summary ",
    )

    assert report.name == "suite"
    assert report.summary == "summary"

    with pytest.raises(ValidationError):
        report.model_copy(update={"total_cases": 3}).__class__(
            **{**report.model_dump(mode="python"), "total_cases": 3}
        )
    with pytest.raises(ValidationError):
        BenchmarkReport(
            **{
                **report.model_dump(mode="python"),
                "results": [_result("same"), _result("SAME", success=False)],
            }
        )
    with pytest.raises(ValidationError):
        BenchmarkReport(
            **{**report.model_dump(mode="python"), "average_score": 0.5}
        )
