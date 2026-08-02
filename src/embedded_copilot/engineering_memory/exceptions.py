from __future__ import annotations


class EngineeringMemoryError(RuntimeError):
    __slots__ = ()


class EngineeringMemoryRequestRejected(EngineeringMemoryError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("MEMORY_REQUEST_REJECTED")


class MemoryPermissionDenied(EngineeringMemoryError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("MEMORY_PERMISSION_DENIED")


class MemoryAuditUnavailable(EngineeringMemoryError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("MEMORY_AUDIT_UNAVAILABLE")


class MemoryStoreUnavailable(EngineeringMemoryError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("MEMORY_STORE_UNAVAILABLE")


class MemoryRevisionConflict(EngineeringMemoryError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("MEMORY_REVISION_CONFLICT")


class MemoryOperationConflict(EngineeringMemoryError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("MEMORY_OPERATION_CONFLICT")


class MemoryStateTransitionRejected(EngineeringMemoryError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("MEMORY_STATE_TRANSITION_REJECTED")


class MemoryRecordNotFound(EngineeringMemoryError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("MEMORY_RECORD_NOT_FOUND")


class MemoryRetrievalError(EngineeringMemoryError):
    __slots__ = ()


class MemoryRetrievalRequestRejected(MemoryRetrievalError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("MEMORY_RETRIEVAL_REQUEST_REJECTED")


class MemoryRetrievalUnavailable(MemoryRetrievalError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("MEMORY_RETRIEVAL_UNAVAILABLE")
