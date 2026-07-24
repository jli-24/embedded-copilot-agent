class BenchmarkError(Exception):
    """Base error for the offline benchmark layer."""


class BenchmarkDatasetError(BenchmarkError):
    """Raised when benchmark dataset data is invalid."""


class BenchmarkRunError(BenchmarkError):
    """Raised when a benchmark run cannot produce a report."""


class BenchmarkEvaluationError(BenchmarkError):
    """Raised when deterministic evaluation cannot be performed."""


class BenchmarkReportError(BenchmarkError):
    """Raised when benchmark report assembly fails."""
