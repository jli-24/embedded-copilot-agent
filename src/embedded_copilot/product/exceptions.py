"""Redacted Product Layer exceptions."""


class ProductError(Exception):
    """Base Product Layer error."""


class ProductProjectionRejected(ProductError):
    """Raised when a caller-owned snapshot fails closed."""


__all__ = ("ProductError", "ProductProjectionRejected")
