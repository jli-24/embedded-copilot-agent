"""Deterministic orchestration for engineering artifact proposals."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from embedded_copilot.engineering_generation.contracts import (
    ArtifactGeneratorPort,
    EngineeringGenerationPort,
    GenerationApprovalPolicyPort,
    GenerationProgressSink,
    GenerationVerificationPort,
    GeneratorCapabilityBinding,
    GeneratorRegistryPort,
)
from embedded_copilot.engineering_generation.exceptions import (
    ArtifactApprovalRejected,
    ArtifactGenerationRejected,
    GenerationProgressUnavailable,
)
from embedded_copilot.engineering_generation.models import (
    ApprovedArtifactReference,
    ArtifactApprovalContext,
    ArtifactApprovalDecision,
    ArtifactGenerationRequest,
    ArtifactGenerationSnapshot,
    ArtifactLifecycleState,
    ArtifactProposal,
    GenerationApprovalPolicyRequest,
    GenerationApprovalPolicyResult,
    GenerationApprovalStatus,
    GenerationFailureCode,
    GenerationProgressEvent,
    GenerationVerificationRequest,
    GenerationVerificationResult,
    GenerationVerificationStatus,
    GeneratorBindingMetadata,
    GeneratorInvocationRequest,
    GeneratorResolutionRequest,
    GeneratorType,
    artifact_generation_snapshot_fingerprint,
)

_ContractT = TypeVar("_ContractT", bound=BaseModel)


def _typed_copy(value: object, expected_type: type[_ContractT]) -> _ContractT:
    """Deep-copy and revalidate a typed contract without serialization."""
    if type(value) is not expected_type:
        raise ArtifactGenerationRejected("generation contract is invalid")
    try:
        copied = value.model_copy(deep=True)
        return expected_type.model_validate(copied)
    except (TypeError, ValueError, ValidationError):
        raise ArtifactGenerationRejected("generation contract is invalid") from None


class _EngineeringGenerationService(EngineeringGenerationPort):
    __slots__ = (
        "__approval_policy",
        "__generator_registry",
        "__progress_sink",
        "__verification_port",
    )

    def __init__(
        self,
        *,
        generator_registry: GeneratorRegistryPort,
        verification_port: GenerationVerificationPort,
        approval_policy: GenerationApprovalPolicyPort,
        progress_sink: GenerationProgressSink,
    ) -> None:
        self.__generator_registry = generator_registry
        self.__verification_port = verification_port
        self.__approval_policy = approval_policy
        self.__progress_sink = progress_sink

    def generate_artifact(
        self, request: ArtifactGenerationRequest
    ) -> ArtifactGenerationSnapshot:
        safe_request = _typed_copy(request, ArtifactGenerationRequest)
        sequence = self._emit(
            request=safe_request,
            state=ArtifactLifecycleState.CREATED,
            sequence=1,
            timestamp=safe_request.timestamp,
        )
        generator_type = GeneratorType(safe_request.artifact_type.value)
        try:
            raw_binding = self.__generator_registry.resolve(
                GeneratorResolutionRequest(
                    generation_id=safe_request.generation_id,
                    generator_type=generator_type,
                )
            )
            binding = self._binding(raw_binding, generator_type)
        except Exception:
            return self._terminal(
                request=safe_request,
                state=ArtifactLifecycleState.FAILED,
                failure_code=GenerationFailureCode.GENERATOR_UNAVAILABLE,
                sequence=sequence,
                timestamp=safe_request.timestamp,
            )

        sequence = self._emit(
            request=safe_request,
            state=ArtifactLifecycleState.GENERATING,
            sequence=sequence + 1,
            timestamp=safe_request.timestamp,
        )
        try:
            raw_proposal = binding.generation_port.generate(
                GeneratorInvocationRequest(request=safe_request)
            )
        except TimeoutError:
            return self._terminal(
                request=safe_request,
                state=ArtifactLifecycleState.FAILED,
                failure_code=GenerationFailureCode.GENERATION_TIMEOUT,
                sequence=sequence,
                timestamp=safe_request.timestamp,
            )
        except Exception:
            return self._terminal(
                request=safe_request,
                state=ArtifactLifecycleState.FAILED,
                failure_code=GenerationFailureCode.GENERATOR_UNAVAILABLE,
                sequence=sequence,
                timestamp=safe_request.timestamp,
            )
        try:
            proposal = _typed_copy(raw_proposal, ArtifactProposal)
            self._validate_proposal(proposal, safe_request)
        except (ArtifactGenerationRejected, ValueError):
            return self._terminal(
                request=safe_request,
                state=ArtifactLifecycleState.FAILED,
                failure_code=GenerationFailureCode.PROPOSAL_REJECTED,
                sequence=sequence,
                timestamp=safe_request.timestamp,
            )

        sequence = self._emit(
            request=safe_request,
            state=ArtifactLifecycleState.VERIFYING,
            sequence=sequence + 1,
            timestamp=safe_request.timestamp,
        )
        try:
            raw_verification = self.__verification_port.verify(
                GenerationVerificationRequest(
                    generation_id=safe_request.generation_id,
                    proposal=proposal,
                    timestamp=safe_request.timestamp,
                )
            )
            verification = _typed_copy(raw_verification, GenerationVerificationResult)
            self._validate_verification(verification, proposal)
        except Exception:
            return self._terminal(
                request=safe_request,
                state=ArtifactLifecycleState.FAILED,
                failure_code=GenerationFailureCode.VERIFICATION_UNAVAILABLE,
                sequence=sequence,
                timestamp=safe_request.timestamp,
            )
        if verification.status is GenerationVerificationStatus.INVALID:
            return self._terminal(
                request=safe_request,
                state=ArtifactLifecycleState.REJECTED,
                failure_code=GenerationFailureCode.VERIFICATION_INVALID,
                sequence=sequence,
                timestamp=safe_request.timestamp,
            )

        sequence = self._emit(
            request=safe_request,
            state=ArtifactLifecycleState.WAITING_APPROVAL,
            sequence=sequence + 1,
            timestamp=safe_request.timestamp,
        )
        return self._snapshot(
            request=safe_request,
            state=ArtifactLifecycleState.WAITING_APPROVAL,
            proposal=proposal,
            progress_sequence=sequence,
        )

    def approve_artifact(
        self,
        snapshot: ArtifactGenerationSnapshot,
        approval: ArtifactApprovalContext,
    ) -> ArtifactGenerationSnapshot:
        try:
            safe_snapshot = _typed_copy(snapshot, ArtifactGenerationSnapshot)
            safe_approval = _typed_copy(approval, ArtifactApprovalContext)
        except ArtifactGenerationRejected:
            raise ArtifactApprovalRejected("artifact approval is rejected") from None
        self._validate_approval(safe_snapshot, safe_approval)
        if safe_approval.decision is ArtifactApprovalDecision.REJECTED:
            return self._terminal(
                request=safe_snapshot.request,
                state=ArtifactLifecycleState.REJECTED,
                failure_code=GenerationFailureCode.APPROVAL_REJECTED,
                sequence=safe_snapshot.progress_sequence,
                timestamp=safe_approval.timestamp,
                proposal=safe_snapshot.proposal,
            )

        proposal = safe_snapshot.proposal
        assert proposal is not None
        try:
            raw_result = self.__approval_policy.authorize(
                GenerationApprovalPolicyRequest(
                    generation_id=safe_snapshot.generation_id,
                    artifact_fingerprint=proposal.fingerprint,
                    workflow_id=safe_snapshot.workflow_id,
                    reviewer=safe_approval.reviewer,
                    timestamp=safe_approval.timestamp,
                )
            )
            policy_result = _typed_copy(raw_result, GenerationApprovalPolicyResult)
            if (
                policy_result.generation_id != safe_snapshot.generation_id
                or policy_result.artifact_fingerprint != proposal.fingerprint
            ):
                raise ValueError("approval policy binding mismatch")
        except Exception:
            return self._terminal(
                request=safe_snapshot.request,
                state=ArtifactLifecycleState.FAILED,
                failure_code=GenerationFailureCode.APPROVAL_UNAVAILABLE,
                sequence=safe_snapshot.progress_sequence,
                timestamp=safe_approval.timestamp,
                proposal=proposal,
            )
        if policy_result.status is GenerationApprovalStatus.DENIED:
            return self._terminal(
                request=safe_snapshot.request,
                state=ArtifactLifecycleState.REJECTED,
                failure_code=GenerationFailureCode.APPROVAL_REJECTED,
                sequence=safe_snapshot.progress_sequence,
                timestamp=safe_approval.timestamp,
                proposal=proposal,
            )

        sequence = self._emit(
            request=safe_snapshot.request,
            state=ArtifactLifecycleState.APPROVED,
            sequence=safe_snapshot.progress_sequence + 1,
            timestamp=safe_approval.timestamp,
        )
        approved_reference = ApprovedArtifactReference(
            generation_id=safe_snapshot.generation_id,
            artifact_type=safe_snapshot.artifact_type,
            proposal_fingerprint=proposal.fingerprint,
        )
        sequence = self._emit(
            request=safe_snapshot.request,
            state=ArtifactLifecycleState.COMPLETED,
            sequence=sequence + 1,
            timestamp=safe_approval.timestamp,
        )
        return self._snapshot(
            request=safe_snapshot.request,
            state=ArtifactLifecycleState.COMPLETED,
            proposal=proposal,
            approved_artifact=approved_reference,
            progress_sequence=sequence,
        )

    def _binding(
        self, value: object, expected_type: GeneratorType
    ) -> GeneratorCapabilityBinding:
        if type(value) is not GeneratorCapabilityBinding:
            raise ArtifactGenerationRejected("generator binding is invalid")
        metadata = _typed_copy(value.metadata, GeneratorBindingMetadata)
        if (
            metadata.generator_type is not expected_type
            or "GENERATE_ARTIFACT" not in metadata.capabilities
            or not isinstance(value.generation_port, ArtifactGeneratorPort)
        ):
            raise ArtifactGenerationRejected("generator binding is invalid")
        return GeneratorCapabilityBinding(
            metadata=metadata,
            generation_port=value.generation_port,
        )

    @staticmethod
    def _validate_proposal(
        proposal: ArtifactProposal, request: ArtifactGenerationRequest
    ) -> None:
        if (
            proposal.generation_id != request.generation_id
            or proposal.workflow_id != request.workflow_id
            or proposal.task_id != request.task_id
            or proposal.artifact_type is not request.artifact_type
        ):
            raise ValueError("proposal binding mismatch")
        verified = set(request.input_context.verified_source_references)
        if any(reference not in verified for reference in proposal.references):
            raise ValueError("proposal reference is not verified")

    @staticmethod
    def _validate_verification(
        verification: GenerationVerificationResult,
        proposal: ArtifactProposal,
    ) -> None:
        if (
            verification.generation_id != proposal.generation_id
            or verification.proposal_fingerprint != proposal.fingerprint
        ):
            raise ValueError("verification binding mismatch")

    @staticmethod
    def _validate_approval(
        snapshot: ArtifactGenerationSnapshot,
        approval: ArtifactApprovalContext,
    ) -> None:
        proposal = snapshot.proposal
        if (
            snapshot.state is not ArtifactLifecycleState.WAITING_APPROVAL
            or proposal is None
            or approval.generation_id != snapshot.generation_id
            or approval.workflow_id != snapshot.workflow_id
            or approval.artifact_fingerprint != proposal.fingerprint
        ):
            raise ArtifactApprovalRejected("artifact approval is rejected")

    def _terminal(
        self,
        *,
        request: ArtifactGenerationRequest,
        state: ArtifactLifecycleState,
        failure_code: GenerationFailureCode,
        sequence: int,
        timestamp,
        proposal: ArtifactProposal | None = None,
    ) -> ArtifactGenerationSnapshot:
        sequence = self._emit(
            request=request,
            state=state,
            sequence=sequence + 1,
            timestamp=timestamp,
        )
        return self._snapshot(
            request=request,
            state=state,
            proposal=proposal,
            failure_code=failure_code,
            progress_sequence=sequence,
        )

    def _emit(
        self,
        *,
        request: ArtifactGenerationRequest,
        state: ArtifactLifecycleState,
        sequence: int,
        timestamp,
    ) -> int:
        event = GenerationProgressEvent(
            sequence=sequence,
            generation_id=request.generation_id,
            workflow_id=request.workflow_id,
            state=state,
            timestamp=timestamp,
        )
        try:
            self.__progress_sink.emit(event)
        except Exception:
            raise GenerationProgressUnavailable(
                "generation progress is unavailable"
            ) from None
        return sequence

    @staticmethod
    def _snapshot(
        *,
        request: ArtifactGenerationRequest,
        state: ArtifactLifecycleState,
        progress_sequence: int,
        proposal: ArtifactProposal | None = None,
        approved_artifact: ApprovedArtifactReference | None = None,
        failure_code: GenerationFailureCode | None = None,
    ) -> ArtifactGenerationSnapshot:
        values = {
            "request": request,
            "state": state,
            "proposal": proposal,
            "approved_artifact": approved_artifact,
            "failure_code": failure_code,
            "progress_sequence": progress_sequence,
        }
        return ArtifactGenerationSnapshot(
            generation_id=request.generation_id,
            workflow_id=request.workflow_id,
            task_id=request.task_id,
            artifact_type=request.artifact_type,
            **values,
            fingerprint=artifact_generation_snapshot_fingerprint(**values),
        )


def _create_engineering_generation_service(
    *,
    generator_registry: GeneratorRegistryPort,
    verification_port: GenerationVerificationPort,
    approval_policy: GenerationApprovalPolicyPort,
    progress_sink: GenerationProgressSink,
) -> EngineeringGenerationPort:
    return _EngineeringGenerationService(
        generator_registry=generator_registry,
        verification_port=verification_port,
        approval_policy=approval_policy,
        progress_sink=progress_sink,
    )
