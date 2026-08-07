class MultimodalUnavailable(Exception):
    """Raised when the injected multimodal boundary is unavailable."""


class MultimodalRejected(Exception):
    """Raised when a multimodal projection fails validation."""


__all__ = ["MultimodalRejected", "MultimodalUnavailable"]
