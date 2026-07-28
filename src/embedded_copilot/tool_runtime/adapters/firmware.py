from __future__ import annotations

from pydantic import Field, field_validator

from embedded_copilot.tool_runtime.models import (
    BuildStatus,
    CompileFirmwareArguments,
    FirmwareBuildOutput,
    ToolAdapterResult,
    ToolBuildSystem,
    ToolCompiler,
    ToolExecutionContext,
    ToolMetric,
    ToolMetricUnit,
    ToolResultStatus,
    _ToolContract,
    _identifier,
    _safe_text,
)
from embedded_copilot.tool_runtime.ports import EngineeringToolPort


class MockBuildScenario(_ToolContract):
    project_id: str
    build_system: ToolBuildSystem
    workspace_reference: str
    build_status: BuildStatus
    compiler: ToolCompiler
    warnings_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    summary: str

    @field_validator("project_id", "workspace_reference", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return _safe_text(value, field="summary")


class _MockFirmwareBuildAdapter:
    __slots__ = ("_scenarios",)

    def __init__(self, scenarios: tuple[MockBuildScenario, ...]) -> None:
        self._scenarios = scenarios

    @property
    def tool_name(self) -> str:
        return "compile_firmware"

    def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        arguments = context.request.arguments
        if not isinstance(arguments, CompileFirmwareArguments):
            return ToolAdapterResult(
                status=ToolResultStatus.REJECTED,
                summary="arguments_mismatch",
            )
        for scenario in self._scenarios:
            if (
                scenario.project_id == arguments.project_id
                and scenario.build_system is arguments.build_system
                and scenario.workspace_reference == arguments.workspace_reference
            ):
                return ToolAdapterResult(
                    status=ToolResultStatus.SUCCESS,
                    summary=scenario.summary,
                    output=FirmwareBuildOutput(
                        build_status=scenario.build_status,
                        compiler=scenario.compiler,
                        warnings_count=scenario.warnings_count,
                        error_count=scenario.error_count,
                        summary=scenario.summary,
                    ),
                    metrics=(
                        ToolMetric(
                            name="error_count",
                            value=scenario.error_count,
                            unit=ToolMetricUnit.COUNT,
                        ),
                        ToolMetric(
                            name="warnings_count",
                            value=scenario.warnings_count,
                            unit=ToolMetricUnit.COUNT,
                        ),
                    ),
                )
        return ToolAdapterResult(
            status=ToolResultStatus.REJECTED,
            summary="mock_scenario_not_found",
        )


def create_mock_firmware_build_adapter(
    *,
    scenarios: tuple[MockBuildScenario, ...],
) -> EngineeringToolPort:
    if not isinstance(scenarios, tuple):
        raise TypeError("scenarios must be a tuple")
    validated = tuple(
        MockBuildScenario.model_validate(item.model_dump(mode="python"))
        for item in scenarios
    )
    keys = tuple(
        (item.project_id, item.build_system, item.workspace_reference)
        for item in validated
    )
    if len(keys) != len(set(keys)):
        raise ValueError("mock build scenarios must be unique")
    return _MockFirmwareBuildAdapter(validated)
