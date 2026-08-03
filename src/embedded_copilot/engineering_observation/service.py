"""Deterministic observation and repair projection service."""

from __future__ import annotations

from embedded_copilot.engineering_observation.models import (
    BuildObservationProjection,
    DebugCategory,
    EngineeringObservation,
    EngineeringObservationType,
    RepairProposal,
    build_observation_projection_fingerprint,
    engineering_observation_fingerprint,
    repair_proposal_fingerprint,
)
from embedded_copilot.execution import BuildResult, BuildStatus


class EngineeringObservationService:
    __slots__ = ()

    def observe(self, result: BuildResult) -> BuildObservationProjection:
        if type(result) is not BuildResult:
            raise TypeError("typed build result is required")
        checked = BuildResult.model_validate(result.model_copy(deep=True))
        observation_type = _observation_type(checked)
        category, suggestions = _repair(checked)
        observation_values = {
            "build_id": checked.build_id,
            "project_id": checked.project_id,
            "source_result_fingerprint": checked.fingerprint,
            "observation_type": observation_type,
            "diagnostic_codes": checked.diagnostic_codes,
        }
        observation = EngineeringObservation(
            **observation_values,
            fingerprint=engineering_observation_fingerprint(**observation_values),
        )
        repair_values = {
            "source_result_fingerprint": checked.fingerprint,
            "category": category,
            "suggestion_codes": suggestions,
            "apply_available": False,
        }
        repair = RepairProposal(
            **repair_values,
            fingerprint=repair_proposal_fingerprint(**repair_values),
        )
        projection_values = {"observation": observation, "repair": repair}
        return BuildObservationProjection(
            **projection_values,
            fingerprint=build_observation_projection_fingerprint(
                **projection_values
            ),
        )


def _observation_type(result: BuildResult) -> EngineeringObservationType:
    if result.status is BuildStatus.SUCCESS:
        return EngineeringObservationType.BUILD_SUCCESS
    if "DEPENDENCY_ERROR" in result.diagnostic_codes:
        return EngineeringObservationType.DEPENDENCY_ERROR
    if {"COMPILER_ERROR", "UNDEFINED_REFERENCE"}.intersection(
        result.diagnostic_codes
    ):
        return EngineeringObservationType.COMPILER_ERROR
    return EngineeringObservationType.BUILD_FAILED


def _repair(result: BuildResult) -> tuple[DebugCategory, tuple[str, ...]]:
    if "DEPENDENCY_ERROR" in result.diagnostic_codes:
        return DebugCategory.MISSING_DEPENDENCY, ("REVIEW_BUILD_DEPENDENCIES",)
    if (
        "UNDEFINED_REFERENCE" in result.diagnostic_codes
        and "esp_camera_init" in result.symbol_references
    ):
        return DebugCategory.MISSING_DEPENDENCY, ("ADD_ESP32_CAMERA_COMPONENT",)
    if {"COMPILER_ERROR", "UNDEFINED_REFERENCE"}.intersection(
        result.diagnostic_codes
    ):
        return DebugCategory.COMPILER_ERROR, ("REVIEW_COMPILER_DIAGNOSTIC",)
    return DebugCategory.UNKNOWN, ()
