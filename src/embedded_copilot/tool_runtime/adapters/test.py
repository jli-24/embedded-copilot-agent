from __future__ import annotations

from pydantic import Field, field_validator

from embedded_copilot.tool_runtime.models import (
    FirmwareTestOutput,
    RunFirmwareTestArguments,
    ToolAdapterResult,
    ToolExecutionContext,
    ToolMetric,
    ToolMetricUnit,
    ToolResultStatus,
    _ToolContract,
    _finite_number,
    _identifier,
    _safe_text,
)
from embedded_copilot.tool_runtime.ports import EngineeringToolPort


class MockTestScenario(_ToolContract):
    project_id: str
    test_id: str
    workspace_reference: str
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    duration_ms: int | float = Field(ge=0)
    summary: str

    @field_validator(
        "project_id",
        "test_id",
        "workspace_reference",
        mode="before",
    )
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("duration_ms", mode="before")
    @classmethod
    def validate_duration(cls, value: object) -> int | float:
        candidate = _finite_number(value)
        if candidate < 0:
            raise ValueError("duration_ms is invalid")
        return candidate

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return _safe_text(value, field="summary")


class _MockFirmwareTestAdapter:
    __slots__ = ("_scenarios",)

    def __init__(self, scenarios: tuple[MockTestScenario, ...]) -> None:
        self._scenarios = scenarios

    @property
    def tool_name(self) -> str:
        return "run_firmware_test"

    def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        arguments = context.request.arguments
        if not isinstance(arguments, RunFirmwareTestArguments):
            return ToolAdapterResult(
                status=ToolResultStatus.REJECTED,
                summary="arguments_mismatch",
            )
        for scenario in self._scenarios:
            if (
                scenario.project_id == arguments.project_id
                and scenario.test_id == arguments.test_id
                and scenario.workspace_reference == arguments.workspace_reference
            ):
                return ToolAdapterResult(
                    status=ToolResultStatus.SUCCESS,
                    summary=scenario.summary,
                    output=FirmwareTestOutput(
                        passed_count=scenario.passed_count,
                        failed_count=scenario.failed_count,
                        duration_ms=scenario.duration_ms,
                        summary=scenario.summary,
                    ),
                    metrics=(
                        ToolMetric(
                            name="duration_ms",
                            value=scenario.duration_ms,
                            unit=ToolMetricUnit.MILLISECONDS,
                        ),
                        ToolMetric(
                            name="failed_count",
                            value=scenario.failed_count,
                            unit=ToolMetricUnit.COUNT,
                        ),
                        ToolMetric(
                            name="passed_count",
                            value=scenario.passed_count,
                            unit=ToolMetricUnit.COUNT,
                        ),
                    ),
                )
        return ToolAdapterResult(
            status=ToolResultStatus.REJECTED,
            summary="mock_scenario_not_found",
        )


def create_mock_firmware_test_adapter(
    *,
    scenarios: tuple[MockTestScenario, ...],
) -> EngineeringToolPort:
    if not isinstance(scenarios, tuple):
        raise TypeError("scenarios must be a tuple")
    validated = tuple(
        MockTestScenario.model_validate(item.model_dump(mode="python"))
        for item in scenarios
    )
    keys = tuple(
        (item.project_id, item.test_id, item.workspace_reference) for item in validated
    )
    if len(keys) != len(set(keys)):
        raise ValueError("mock test scenarios must be unique")
    return _MockFirmwareTestAdapter(validated)
