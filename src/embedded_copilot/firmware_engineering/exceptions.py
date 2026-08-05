class FirmwareEngineeringError(RuntimeError):
    code = "FIRMWARE_UNAVAILABLE"


class FirmwareUnavailable(FirmwareEngineeringError):
    code = "FIRMWARE_UNAVAILABLE"


class FirmwareRejected(FirmwareEngineeringError):
    code = "FIRMWARE_REJECTED"


class BuildApprovalRequired(FirmwareEngineeringError):
    code = "BUILD_APPROVAL_REQUIRED"


class BuildUnavailable(FirmwareEngineeringError):
    code = "BUILD_UNAVAILABLE"


class BuildFailed(FirmwareEngineeringError):
    code = "BUILD_FAILED"


class FirmwareNotFound(FirmwareEngineeringError):
    code = "FIRMWARE_NOT_FOUND"


class FirmwareDebugRejected(FirmwareEngineeringError):
    code = "FIRMWARE_REJECTED"
