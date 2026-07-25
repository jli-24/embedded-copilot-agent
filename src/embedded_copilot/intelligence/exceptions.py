class IntelligenceError(RuntimeError):
    """Base error for the provider-neutral Intelligence Layer."""


class ModelGatewayError(IntelligenceError):
    """Raised when a model provider fails or returns an invalid result."""


class ModelProviderUnavailable(ModelGatewayError):
    """Raised when no eligible model provider is available."""
