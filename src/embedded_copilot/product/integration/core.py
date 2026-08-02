"""Deep-copy and minimize public v0.50-v0.57 contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError, field_validator, model_validator

from embedded_copilot.engineering_artifacts import EngineeringArtifactContract
from embedded_copilot.engineering_execution import (
    EngineeringExecutionReport,
    EngineeringExecutionState,
    ExecutionApprovalStatus,
)
from embedded_copilot.engineering_feedback import (
    EngineeringFeedbackReport,
    FeedbackItemType,
)
from embedded_copilot.engineering_firmware import FirmwareEngineeringProposal
from embedded_copilot.engineering_hardware import HardwareEngineeringProposal
from embedded_copilot.engineering_intelligence import (
    EngineeringContextSnapshot,
    EngineeringProjectPlan,
    EngineeringRequirementDocument,
)
from embedded_copilot.engineering_optimization import EngineeringOptimizationReport
from embedded_copilot.engineering_validation import HardwareValidationReport
from embedded_copilot.product.models import (
    ProductDecisionProjection,
    ProductReference,
    ProductReferenceType,
    ProductStage,
    ProductStageStatus,
    _ProductModel,
    _fingerprint,
    _fp,
    _identifier,
    _text,
    _tuple,
    _utc,
    product_reference_fingerprint,
)


def _typed_copy(value: object, expected_type: type):
    if type(value) is not expected_type:
        raise ValueError("typed Engineering Core contract is required")
    copied = value.model_copy(deep=True)
    return expected_type.model_validate(copied)


class CreateProjectRequest(_ProductModel):
    project_id: str
    project_name: str
    project_summary: str
    session_id: str
    requirement: EngineeringRequirementDocument | None = None
    plan: EngineeringProjectPlan | None = None
    context: EngineeringContextSnapshot | None = None
    hardware_proposal: HardwareEngineeringProposal | None = None
    firmware_proposal: FirmwareEngineeringProposal | None = None
    validation_report: HardwareValidationReport | None = None
    artifact_contract: EngineeringArtifactContract | None = None
    execution_report: EngineeringExecutionReport | None = None
    feedback_report: EngineeringFeedbackReport | None = None
    optimization_report: EngineeringOptimizationReport | None = None
    decisions: tuple[ProductDecisionProjection, ...]
    created_at: datetime
    fingerprint: str

    _project_id = field_validator("project_id")(
        lambda value: _identifier(value, field="project_id")
    )
    _name = field_validator("project_name")(
        lambda value: _text(value, field="project_name", limit=128)
    )
    _summary = field_validator("project_summary")(
        lambda value: _text(value, field="project_summary")
    )
    _session_id = field_validator("session_id")(
        lambda value: _identifier(value, field="session_id")
    )
    _created_at = field_validator("created_at")(
        lambda value: _utc(value, field="created_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fp)

    @field_validator("decisions", mode="before")
    @classmethod
    def validate_decisions_tuple(cls, value: object) -> object:
        return _tuple(value, field="decisions")

    @field_validator("requirement", mode="before")
    @classmethod
    def validate_requirement(cls, value: object):
        return _optional_copy(value, EngineeringRequirementDocument)

    @field_validator("plan", mode="before")
    @classmethod
    def validate_plan(cls, value: object):
        return _optional_copy(value, EngineeringProjectPlan)

    @field_validator("context", mode="before")
    @classmethod
    def validate_context(cls, value: object):
        return _optional_copy(value, EngineeringContextSnapshot)

    @field_validator("hardware_proposal", mode="before")
    @classmethod
    def validate_hardware(cls, value: object):
        return _optional_copy(value, HardwareEngineeringProposal)

    @field_validator("firmware_proposal", mode="before")
    @classmethod
    def validate_firmware(cls, value: object):
        return _optional_copy(value, FirmwareEngineeringProposal)

    @field_validator("validation_report", mode="before")
    @classmethod
    def validate_validation(cls, value: object):
        return _optional_copy(value, HardwareValidationReport)

    @field_validator("artifact_contract", mode="before")
    @classmethod
    def validate_artifact(cls, value: object):
        return _optional_copy(value, EngineeringArtifactContract)

    @field_validator("execution_report", mode="before")
    @classmethod
    def validate_execution(cls, value: object):
        return _optional_copy(value, EngineeringExecutionReport)

    @field_validator("feedback_report", mode="before")
    @classmethod
    def validate_feedback(cls, value: object):
        return _optional_copy(value, EngineeringFeedbackReport)

    @field_validator("optimization_report", mode="before")
    @classmethod
    def validate_optimization(cls, value: object):
        return _optional_copy(value, EngineeringOptimizationReport)

    @model_validator(mode="after")
    def validate_request(self) -> CreateProjectRequest:
        decision_ids = tuple(item.decision_id for item in self.decisions)
        if decision_ids != tuple(sorted(decision_ids)) or len(decision_ids) != len(
            set(decision_ids)
        ):
            raise ValueError("decisions must be sorted and unique")
        values = {
            name: getattr(self, name)
            for name in type(self).model_fields
            if name != "fingerprint"
        }
        if self.fingerprint != create_project_request_fingerprint(**values):
            raise ValueError("create project request fingerprint mismatch")
        return self


def _optional_copy(value: object, expected_type: type):
    return None if value is None else _typed_copy(value, expected_type)


def create_project_request_fingerprint(**values: object) -> str:
    return _fingerprint("CreateProjectRequest", **values)


@dataclass(frozen=True, slots=True)
class ProjectCoreProjection:
    request: CreateProjectRequest
    stages: tuple[
        tuple[ProductStage, ProductStageStatus, tuple[ProductReference, ...]], ...
    ]
    pending_reviews: int
    approved: int
    rejected: int
    change_requests: int
    review_reference_ids: tuple[str, ...]


def project_core(value: object) -> ProjectCoreProjection:
    if type(value) is not CreateProjectRequest:
        raise TypeError("typed create project request is required")
    try:
        checked = CreateProjectRequest.model_validate(value.model_copy(deep=True))
        _validate_bindings(checked)
        references = _references(checked)
        statuses = _stage_statuses(checked, references)
        pending, approved, rejected, changes, review_ids = _review_counts(checked)
    except (TypeError, ValueError, ValidationError):
        raise ValueError("product request is invalid") from None
    return ProjectCoreProjection(
        request=checked,
        stages=tuple(
            (stage, statuses[stage], references.get(stage, ()))
            for stage in ProductStage
        ),
        pending_reviews=pending,
        approved=approved,
        rejected=rejected,
        change_requests=changes,
        review_reference_ids=review_ids,
    )


def _validate_bindings(request: CreateProjectRequest) -> None:
    requirement = request.requirement
    plan = request.plan
    context = request.context
    hardware = request.hardware_proposal
    firmware = request.firmware_proposal
    validation = request.validation_report
    artifact = request.artifact_contract
    execution = request.execution_report
    feedback = request.feedback_report
    optimization = request.optimization_report
    if requirement is not None and requirement.project_id != request.project_id:
        raise ValueError("requirement binding mismatch")
    if plan is not None and (
        requirement is None
        or plan.project_id != request.project_id
        or plan.requirement_fingerprint != requirement.fingerprint
    ):
        raise ValueError("plan binding mismatch")
    if context is not None and (
        requirement is None
        or context.project.project_id != request.project_id
        or context.requirement_fingerprint != requirement.fingerprint
        or (plan is not None and context.plan_fingerprint != plan.fingerprint)
    ):
        raise ValueError("context binding mismatch")
    if hardware is not None and (
        context is None
        or hardware.project_id != request.project_id
        or hardware.requirement_fingerprint != requirement.fingerprint
        or hardware.plan_fingerprint != context.plan_fingerprint
        or hardware.context_fingerprint != context.fingerprint
    ):
        raise ValueError("hardware binding mismatch")
    if firmware is not None and (
        hardware is None
        or firmware.project_id != request.project_id
        or firmware.hardware_proposal_fingerprint != hardware.fingerprint
        or firmware.requirement_fingerprint != requirement.fingerprint
        or firmware.plan_fingerprint != context.plan_fingerprint
        or firmware.context_fingerprint != context.fingerprint
    ):
        raise ValueError("firmware binding mismatch")
    if validation is not None and (
        firmware is None
        or validation.project_id != request.project_id
        or validation.hardware_proposal_fingerprint != hardware.fingerprint
        or validation.firmware_proposal_fingerprint != firmware.fingerprint
        or validation.requirement_fingerprint != requirement.fingerprint
        or validation.plan_fingerprint != context.plan_fingerprint
        or validation.context_fingerprint != context.fingerprint
    ):
        raise ValueError("validation binding mismatch")
    if artifact is not None:
        if firmware is None:
            raise ValueError("artifact prerequisites are missing")
        sources = {
            source.source_fingerprint
            for binding in artifact.source_bindings
            for source in binding.sources
        }
        if not {
            requirement.fingerprint,
            context.fingerprint,
            hardware.fingerprint,
            firmware.fingerprint,
        }.issubset(sources):
            raise ValueError("artifact binding mismatch")
    if execution is not None and (
        artifact is None
        or execution.artifact_fingerprint != artifact.fingerprint
        or execution.execution_contract.artifact_source_fingerprint
        != artifact.artifact_source_fingerprint
    ):
        raise ValueError("execution binding mismatch")
    if feedback is not None and (
        artifact is None
        or feedback.feedback.artifact_contract_fingerprint != artifact.fingerprint
        or feedback.feedback.artifact_source_fingerprint
        != artifact.artifact_source_fingerprint
    ):
        raise ValueError("feedback binding mismatch")
    if optimization is not None and (
        artifact is None
        or optimization.artifact_contract_fingerprint != artifact.fingerprint
        or optimization.artifact_source_fingerprint
        != artifact.artifact_source_fingerprint
    ):
        raise ValueError("optimization binding mismatch")
    evidence_ids = (
        {item.evidence_id for item in context.evidence}
        if context is not None
        else set()
    )
    feedback_ids = {feedback.feedback.feedback_id} if feedback is not None else set()
    for decision in request.decisions:
        if not set(decision.evidence_references).issubset(evidence_ids) or not set(
            decision.feedback_references
        ).issubset(feedback_ids):
            raise ValueError("decision reference binding mismatch")


def _reference(
    kind: ProductReferenceType, reference_id: str, source
) -> ProductReference:
    values = dict(
        reference_type=kind,
        reference_id=reference_id,
        source_fingerprint=source.fingerprint,
    )
    return ProductReference(
        **values,
        fingerprint=product_reference_fingerprint(**values),
    )


def _references(
    request: CreateProjectRequest,
) -> dict[ProductStage, tuple[ProductReference, ...]]:
    result: dict[ProductStage, tuple[ProductReference, ...]] = {}
    pairs = (
        (
            ProductStage.REQUIREMENT,
            ProductReferenceType.REQUIREMENT,
            request.requirement,
            "message_id",
        ),
        (
            ProductStage.ARCHITECTURE,
            (
                ProductReferenceType.ARCHITECTURE
                if request.plan is not None
                else ProductReferenceType.CONTEXT
            ),
            request.plan if request.plan is not None else request.context,
            None,
        ),
        (
            ProductStage.HARDWARE,
            ProductReferenceType.HARDWARE,
            request.hardware_proposal,
            "proposal_id",
        ),
        (
            ProductStage.FIRMWARE,
            ProductReferenceType.FIRMWARE,
            request.firmware_proposal,
            "proposal_id",
        ),
        (
            ProductStage.VALIDATION,
            ProductReferenceType.VALIDATION,
            request.validation_report,
            "proposal_id",
        ),
        (
            ProductStage.ARTIFACT,
            ProductReferenceType.ARTIFACT,
            request.artifact_contract,
            None,
        ),
        (
            ProductStage.EXECUTION,
            ProductReferenceType.EXECUTION,
            request.execution_report,
            "execution_id",
        ),
        (
            ProductStage.FEEDBACK,
            ProductReferenceType.FEEDBACK,
            request.feedback_report,
            None,
        ),
        (
            ProductStage.OPTIMIZATION,
            ProductReferenceType.OPTIMIZATION,
            request.optimization_report,
            "request_id",
        ),
    )
    for stage, kind, source, id_field in pairs:
        if source is None:
            continue
        if kind is ProductReferenceType.FEEDBACK:
            reference_id = source.feedback.feedback_id
        else:
            reference_id = (
                source.fingerprint if id_field is None else getattr(source, id_field)
            )
        refs = [_reference(kind, reference_id, source)]
        if (
            stage is ProductStage.ARCHITECTURE
            and request.plan is not None
            and request.context is not None
        ):
            refs.append(
                _reference(
                    ProductReferenceType.CONTEXT,
                    request.context.fingerprint,
                    request.context,
                )
            )
        result[stage] = tuple(refs)
    return result


def _stage_statuses(request, references) -> dict[ProductStage, ProductStageStatus]:
    statuses = {
        stage: (
            ProductStageStatus.COMPLETED
            if references.get(stage)
            else ProductStageStatus.NOT_STARTED
        )
        for stage in ProductStage
    }
    if (
        request.execution_report is not None
        and request.execution_report.execution_status
        in {
            EngineeringExecutionState.BLOCKED,
            EngineeringExecutionState.FAILED,
        }
    ):
        statuses[ProductStage.EXECUTION] = ProductStageStatus.BLOCKED
    missing = next(
        (
            stage
            for stage in ProductStage
            if statuses[stage] is ProductStageStatus.NOT_STARTED
        ),
        None,
    )
    if missing is not None:
        statuses[missing] = ProductStageStatus.IN_PROGRESS
    return statuses


def _review_counts(request):
    pending = approved = rejected = changes = 0
    references = []
    if request.execution_report is not None:
        approval = request.execution_report.review.approval_status
        approved += approval is ExecutionApprovalStatus.APPROVED
        rejected += approval is ExecutionApprovalStatus.REJECTED
        pending += approval is ExecutionApprovalStatus.PENDING
        references.append(request.execution_report.execution_id)
    if request.feedback_report is not None:
        pending += request.feedback_report.review_required
        references.append(request.feedback_report.feedback.feedback_id)
        for item in request.feedback_report.feedback.items:
            approved += item.type is FeedbackItemType.APPROVE
            rejected += item.type is FeedbackItemType.REJECT
            changes += item.type is FeedbackItemType.REQUEST_CHANGE
    return pending, approved, rejected, changes, tuple(sorted(references))


__all__ = ("CreateProjectRequest", "create_project_request_fingerprint")
