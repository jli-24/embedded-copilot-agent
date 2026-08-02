"""Composition root for the Engineering Generation Runtime."""

from embedded_copilot.engineering_generation.contracts import (
    GenerationApprovalPolicyPort,
    GenerationProgressSink,
    GenerationVerificationPort,
    GeneratorRegistryPort,
)
from embedded_copilot.engineering_generation.exceptions import (
    ArtifactGenerationRejected,
)
from embedded_copilot.engineering_generation.facade import (
    EngineeringGenerationRuntime,
)
from embedded_copilot.engineering_generation.runtime import (
    _create_engineering_generation_service,
)


def create_engineering_generation_runtime(
    *,
    generator_registry: GeneratorRegistryPort,
    verification_port: GenerationVerificationPort,
    approval_policy: GenerationApprovalPolicyPort,
    progress_sink: GenerationProgressSink,
) -> EngineeringGenerationRuntime:
    """Create the runtime from caller-owned Protocol implementations."""
    if not isinstance(generator_registry, GeneratorRegistryPort):
        raise ArtifactGenerationRejected("generator registry is invalid")
    if not isinstance(verification_port, GenerationVerificationPort):
        raise ArtifactGenerationRejected("verification port is invalid")
    if not isinstance(approval_policy, GenerationApprovalPolicyPort):
        raise ArtifactGenerationRejected("approval policy is invalid")
    if not isinstance(progress_sink, GenerationProgressSink):
        raise ArtifactGenerationRejected("progress sink is invalid")
    return EngineeringGenerationRuntime._compose(
        _create_engineering_generation_service(
            generator_registry=generator_registry,
            verification_port=verification_port,
            approval_policy=approval_policy,
            progress_sink=progress_sink,
        )
    )
