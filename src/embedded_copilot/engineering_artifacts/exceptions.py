"""Sanitized Engineering Artifact errors."""


class EngineeringArtifactError(Exception):
    """Base Engineering Artifact error."""


class EngineeringArtifactRejected(EngineeringArtifactError):
    """Raised when typed source binding fails closed validation."""
