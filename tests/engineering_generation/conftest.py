from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.engineering_generation import (
    ArtifactApprovalContext,
    ArtifactApprovalDecision,
    ArtifactGenerationRequest,
    ArtifactProposal,
    ArtifactType,
    BOMItem,
    BOMStructuredOutput,
    FirmwareStructuredOutput,
    GenerationApprovalPolicyResult,
    GenerationApprovalStatus,
    GenerationContextProjection,
    GenerationContextReference,
    GenerationReferenceType,
    GenerationVerificationResult,
    GenerationVerificationStatus,
    GeneratorBindingMetadata,
    GeneratorCapabilityBinding,
    GeneratorType,
    HardwareDesignStructuredOutput,
    PCBDesignStructuredOutput,
    artifact_proposal_fingerprint,
    generation_approval_policy_result_fingerprint,
    generation_verification_result_fingerprint,
    generator_binding_fingerprint,
)

NOW = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)
REVIEWED_AT = datetime(2026, 8, 4, 10, 0, tzinfo=UTC)


def request_for(
    *, artifact_type: ArtifactType = ArtifactType.HARDWARE_DESIGN
) -> ArtifactGenerationRequest:
    return ArtifactGenerationRequest(
        generation_id="generation-1",
        workflow_id="workflow-1",
        task_id="task-a",
        artifact_type=artifact_type,
        input_context=GenerationContextProjection(
            summary="Prepare a reviewable engineering artifact proposal.",
            references=(
                GenerationContextReference(
                    reference_type=GenerationReferenceType.DESIGN_REFERENCE,
                    reference_id="design-reference-1",
                ),
            ),
            verified_source_references=(
                GenerationContextReference(
                    reference_type=GenerationReferenceType.DATASHEET_REFERENCE,
                    reference_id="datasheet-reference-1",
                ),
            ),
        ),
        constraints=("Do not modify project files.",),
        timestamp=NOW,
    )


def structured_output_for(artifact_type: ArtifactType):
    if artifact_type is ArtifactType.HARDWARE_DESIGN:
        return HardwareDesignStructuredOutput(
            mcu="ESP32-S3",
            peripherals=("CAMERA_INTERFACE",),
            communications=("WIFI",),
            power_architecture="3V3_REGULATED",
        )
    if artifact_type is ArtifactType.FIRMWARE:
        return FirmwareStructuredOutput(
            project_structure=("APPLICATION", "BSP", "DRIVERS"),
            bsp=("BOARD_SUPPORT",),
            drivers=("CAMERA_DRIVER",),
            middleware=("EVENT_PIPELINE",),
            application=("CAPTURE_SERVICE",),
            freertos_tasks=("CAPTURE_TASK",),
        )
    if artifact_type is ArtifactType.PCB_DESIGN:
        return PCBDesignStructuredOutput(
            placement_rules=("PLACE_DECOUPLING_NEAR_DEVICE",),
            routing_constraints=("REVIEW_HIGH_SPEED_RETURN_PATH",),
            layer_suggestion="REVIEW_REQUIRED",
        )
    return BOMStructuredOutput(
        items=(
            BOMItem(
                component="PRIMARY_COMPONENT",
                alternative="REVIEW_ALTERNATIVE",
                cost=1.0,
                supply_risk="UNKNOWN",
            ),
        )
    )


def proposal_for(request: ArtifactGenerationRequest) -> ArtifactProposal:
    values = {
        "generation_id": request.generation_id,
        "workflow_id": request.workflow_id,
        "task_id": request.task_id,
        "artifact_type": request.artifact_type,
        "summary": "Generated proposal requires engineering review.",
        "structured_output": structured_output_for(request.artifact_type),
        "references": request.input_context.verified_source_references,
        "metrics": (),
    }
    return ArtifactProposal(
        **values,
        fingerprint=artifact_proposal_fingerprint(**values),
    )


class RecordingGenerator:
    def __init__(self, proposal=None, *, error: Exception | None = None) -> None:
        self.proposal = proposal
        self.error = error
        self.calls = []

    def generate(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.proposal


def binding_for(generator: RecordingGenerator, *, generator_type: GeneratorType):
    values = {
        "generator_type": generator_type,
        "capabilities": ("GENERATE_ARTIFACT",),
    }
    metadata = GeneratorBindingMetadata(
        **values,
        fingerprint=generator_binding_fingerprint(**values),
    )
    return GeneratorCapabilityBinding(metadata=metadata, generation_port=generator)


class StaticRegistry:
    def __init__(self, binding=None, *, error: Exception | None = None) -> None:
        self.binding = binding
        self.error = error
        self.calls = []

    def resolve(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.binding


class RecordingVerifier:
    def __init__(
        self,
        *,
        status: GenerationVerificationStatus = GenerationVerificationStatus.VALID,
        error: Exception | None = None,
    ) -> None:
        self.status = status
        self.error = error
        self.calls = []

    def verify(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        values = {
            "generation_id": request.generation_id,
            "proposal_fingerprint": request.proposal.fingerprint,
            "status": self.status,
        }
        return GenerationVerificationResult(
            **values,
            fingerprint=generation_verification_result_fingerprint(**values),
        )


class RecordingApprovalPolicy:
    def __init__(
        self,
        *,
        status: GenerationApprovalStatus = GenerationApprovalStatus.ALLOWED,
        error: Exception | None = None,
    ) -> None:
        self.status = status
        self.error = error
        self.calls = []

    def authorize(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        values = {
            "generation_id": request.generation_id,
            "artifact_fingerprint": request.artifact_fingerprint,
            "status": self.status,
        }
        return GenerationApprovalPolicyResult(
            **values,
            fingerprint=generation_approval_policy_result_fingerprint(**values),
        )


class RecordingProgressSink:
    def __init__(self, *, fail_at: int | None = None) -> None:
        self.events = []
        self.fail_at = fail_at

    def emit(self, event):
        if event.sequence == self.fail_at:
            raise RuntimeError("database path C:/private and token=secret")
        self.events.append(event)


def approval_for(snapshot, decision: ArtifactApprovalDecision):
    assert snapshot.proposal is not None
    return ArtifactApprovalContext(
        generation_id=snapshot.generation_id,
        artifact_fingerprint=snapshot.proposal.fingerprint,
        workflow_id=snapshot.workflow_id,
        decision=decision,
        reviewer="engineer-1",
        timestamp=REVIEWED_AT,
    )


@pytest.fixture
def generation_request() -> ArtifactGenerationRequest:
    return request_for()
