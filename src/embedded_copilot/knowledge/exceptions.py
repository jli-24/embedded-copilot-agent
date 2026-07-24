class KnowledgeGatewayError(Exception):
    """Raised when a unified knowledge search cannot complete safely."""


class KnowledgeProviderError(Exception):
    """Raised when a knowledge provider cannot complete safely."""


class ProviderError(KnowledgeProviderError):
    """Base error for provider lifecycle and execution failures."""


class ProviderUnavailable(ProviderError):
    """Raised when a configured provider cannot be used."""


class ProviderInvalidResult(ProviderError):
    """Raised when a provider violates its boundary contract."""
