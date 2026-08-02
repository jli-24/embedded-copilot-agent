"""Sanitized Web API failures."""


class WebApiError(Exception):
    """Base Web API boundary failure."""


class WebProjectNotFound(WebApiError):
    """The requested project is unavailable."""


class WebRequestRejected(WebApiError):
    """The request or dependency result is invalid."""


class WebDependencyUnavailable(WebApiError):
    """A required injected dependency is unavailable."""
