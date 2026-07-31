"""Protocol boundaries for the Engineering Generation Runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from embedded_copilot.engineering_generation.models import (
    ArtifactApprovalContext,
    ArtifactGenerationRequest,
    ArtifactGenerationSnapshot,
    ArtifactProposal,
    GenerationApprovalPolicyRequest,
    GenerationApprovalPolicyResult,
    GenerationProgressEvent,
    GenerationVerificationRequest,
    GenerationVerificationResult,
    GeneratorBindingMetadata,
    GeneratorInvocationRequest,
    GeneratorResolutionRequest,
)


@runtime_checkable
class EngineeringGenerationPort(Protocol):
    def generate_artifact(
        self, request: ArtifactGenerationRequest
    ) -> ArtifactGenerationSnapshot: ...

    def approve_artifact(
        self,
        snapshot: ArtifactGenerationSnapshot,
        approval: ArtifactApprovalContext,
    ) -> ArtifactGenerationSnapshot: ...


@runtime_checkable
class ArtifactGeneratorPort(Protocol):
    def generate(self, request: GeneratorInvocationRequest) -> ArtifactProposal: ...


@dataclass(frozen=True, slots=True)
class GeneratorCapabilityBinding:
    metadata: GeneratorBindingMetadata
    generation_port: ArtifactGeneratorPort


@runtime_checkable
class GeneratorRegistryPort(Protocol):
    def resolve(
        self, request: GeneratorResolutionRequest
    ) -> GeneratorCapabilityBinding: ...


@runtime_checkable
class GenerationVerificationPort(Protocol):
    def verify(
        self, request: GenerationVerificationRequest
    ) -> GenerationVerificationResult: ...


@runtime_checkable
class GenerationApprovalPolicyPort(Protocol):
    def authorize(
        self, request: GenerationApprovalPolicyRequest
    ) -> GenerationApprovalPolicyResult: ...


@runtime_checkable
class GenerationProgressSink(Protocol):
    def emit(self, event: GenerationProgressEvent) -> None: ...
