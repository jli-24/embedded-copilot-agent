class HILError(RuntimeError):
    code = "HIL_FAILED"


class HILApprovalRequired(HILError):
    code = "HIL_APPROVAL_REQUIRED"


class HILUnavailable(HILError):
    code = "HIL_FAILED"


class HILRejected(HILError):
    code = "HIL_REJECTED"


class DeviceUnavailable(HILError):
    code = "DEVICE_UNAVAILABLE"


class ObservationUnavailable(HILError):
    code = "OBSERVATION_UNAVAILABLE"


class HILResultNotFound(HILError):
    code = "HIL_RESULT_NOT_FOUND"


__all__ = [
    "DeviceUnavailable",
    "HILApprovalRequired",
    "HILError",
    "HILRejected",
    "HILResultNotFound",
    "HILUnavailable",
    "ObservationUnavailable",
]
