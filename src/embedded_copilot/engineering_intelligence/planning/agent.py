"""Fixed, review-only engineering task tree generation."""

from __future__ import annotations

from embedded_copilot.engineering_intelligence.models import (
    EngineeringProjectPlan,
    EngineeringRequirementDocument,
    EngineeringTask,
    EngineeringTaskDomain,
    EstimatedEffort,
    project_plan_fingerprint,
)


class _PlanningAgent:
    def plan(
        self,
        requirement: EngineeringRequirementDocument,
    ) -> EngineeringProjectPlan:
        checked = _typed_copy(requirement, EngineeringRequirementDocument)
        tasks = (
            EngineeringTask(
                task_id="01-hardware",
                domain=EngineeringTaskDomain.HARDWARE,
                summary="Review hardware requirements and component constraints.",
                dependencies=(),
                estimated_effort=EstimatedEffort.MEDIUM,
                engineering_risk="REQUIREMENT_VALIDATION_REQUIRED",
                milestone="HARDWARE_SCOPE_READY",
            ),
            EngineeringTask(
                task_id="02-pcb",
                domain=EngineeringTaskDomain.PCB,
                summary="Prepare a review-only PCB planning boundary.",
                dependencies=("01-hardware",),
                estimated_effort=EstimatedEffort.LARGE,
                engineering_risk="PCB_CONSTRAINT_UNKNOWN",
                milestone="PCB_PLAN_READY",
            ),
            EngineeringTask(
                task_id="03-firmware",
                domain=EngineeringTaskDomain.FIRMWARE,
                summary="Prepare a review-only firmware planning boundary.",
                dependencies=("01-hardware",),
                estimated_effort=EstimatedEffort.LARGE,
                engineering_risk="FIRMWARE_DEPENDENCY",
                milestone="FIRMWARE_PLAN_READY",
            ),
            EngineeringTask(
                task_id="04-testing",
                domain=EngineeringTaskDomain.TESTING,
                summary="Define verification and test planning candidates.",
                dependencies=("02-pcb", "03-firmware"),
                estimated_effort=EstimatedEffort.MEDIUM,
                engineering_risk="VERIFICATION_REQUIRED",
                milestone="TEST_PLAN_READY",
            ),
            EngineeringTask(
                task_id="05-optimization",
                domain=EngineeringTaskDomain.OPTIMIZATION,
                summary="Prepare mathematical optimization review candidates.",
                dependencies=("04-testing",),
                estimated_effort=EstimatedEffort.SMALL,
                engineering_risk="MEASUREMENT_REQUIRED",
                milestone="OPTIMIZATION_REVIEW_READY",
            ),
        )
        milestones = tuple(sorted(task.milestone for task in tasks))
        values = dict(
            project_id=checked.project_id,
            requirement_fingerprint=checked.fingerprint,
            tasks=tasks,
            milestones=milestones,
            review_required=True,
        )
        return EngineeringProjectPlan(
            **values,
            fingerprint=project_plan_fingerprint(**values),
        )


def _typed_copy(value: object, expected_type):
    if type(value) is not expected_type:
        raise TypeError("typed requirement document is required")
    copied = value.model_copy(deep=True)
    return expected_type.model_validate(copied)
