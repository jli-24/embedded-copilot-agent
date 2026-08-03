from __future__ import annotations

from datetime import UTC, datetime

from embedded_copilot.engineering_observation import (
    DebugCategory,
    EngineeringObservationType,
    create_engineering_observation_service,
)
from embedded_copilot.execution import (
    BuildResult,
    BuildStatus,
    build_result_fingerprint,
)

NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)


def _result(
    status: BuildStatus,
    codes: tuple[str, ...],
    symbols: tuple[str, ...] = (),
) -> BuildResult:
    values = {
        "build_id": "build-1",
        "project_id": "project-1",
        "proposal_fingerprint": "sha256:" + "a" * 64,
        "status": status,
        "diagnostic_codes": codes,
        "symbol_references": symbols,
        "observed_at": NOW,
    }
    return BuildResult(**values, fingerprint=build_result_fingerprint(**values))


def test_observation_projects_safe_build_status_and_debug_repair() -> None:
    service = create_engineering_observation_service()
    result = _result(
        BuildStatus.FAILED,
        ("UNDEFINED_REFERENCE",),
        ("esp_camera_init",),
    )
    before = result.model_dump(mode="json")

    projection = service.observe(result)

    assert projection.observation.observation_type is EngineeringObservationType.COMPILER_ERROR
    assert projection.repair.category is DebugCategory.MISSING_DEPENDENCY
    assert projection.repair.suggestion_codes == ("ADD_ESP32_CAMERA_COMPONENT",)
    assert projection.repair.apply_available is False
    assert result.model_dump(mode="json") == before
    serialized = projection.model_dump_json().lower()
    assert "path" not in serialized
    assert "command" not in serialized


def test_success_and_dependency_error_are_exact_code_mappings() -> None:
    service = create_engineering_observation_service()
    success = service.observe(_result(BuildStatus.SUCCESS, ()))
    dependency = service.observe(
        _result(BuildStatus.FAILED, ("DEPENDENCY_ERROR",))
    )

    assert success.observation.observation_type is EngineeringObservationType.BUILD_SUCCESS
    assert dependency.observation.observation_type is EngineeringObservationType.DEPENDENCY_ERROR
    assert dependency.repair.category is DebugCategory.MISSING_DEPENDENCY
