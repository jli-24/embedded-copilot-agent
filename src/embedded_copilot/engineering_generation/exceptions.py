"""Sanitized Engineering Generation Runtime exceptions."""


class EngineeringGenerationError(RuntimeError):
    """Base error for the Engineering Generation Runtime."""


class ArtifactGenerationRejected(EngineeringGenerationError):
    """Raised when a generation boundary contract is invalid."""


class ArtifactApprovalRejected(EngineeringGenerationError):
    """Raised when approval is invalid or does not match the artifact."""


class GenerationProgressUnavailable(EngineeringGenerationError):
    """Raised when a progress event cannot be delivered safely."""
