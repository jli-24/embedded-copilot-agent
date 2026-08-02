"""Framework-independent Engineering Interface projection boundary."""

from embedded_copilot.engineering_interface.contracts import EngineeringInterfacePort
from embedded_copilot.engineering_interface.exceptions import (
    EngineeringInterfaceError,
    EngineeringInterfaceRejected,
    EngineeringWorkflowUnavailable,
)
from embedded_copilot.engineering_interface.facade import EngineeringInterfaceRuntime
from embedded_copilot.engineering_interface.factory import (
    create_engineering_interface_runtime,
)
from embedded_copilot.engineering_interface.models import (
    AttachmentProjectionRequest,
    AttachmentProjectionType,
    EngineeringAttachmentProjection,
    EngineeringChatRequest,
    EngineeringChatRole,
    EngineeringMessageProjection,
    EngineeringProgressEvent,
    EngineeringProgressSource,
    EngineeringProjectProjection,
    EngineeringSessionCreateRequest,
    EngineeringSessionSnapshot,
    EngineeringWorkflowPreparationRequest,
    EngineeringWorkflowUIProjection,
    HumanReviewUIProjection,
    engineering_project_fingerprint,
)

__all__ = (
    "AttachmentProjectionRequest",
    "AttachmentProjectionType",
    "EngineeringAttachmentProjection",
    "EngineeringChatRequest",
    "EngineeringChatRole",
    "EngineeringInterfaceError",
    "EngineeringInterfacePort",
    "EngineeringInterfaceRejected",
    "EngineeringInterfaceRuntime",
    "EngineeringMessageProjection",
    "EngineeringProgressEvent",
    "EngineeringProgressSource",
    "EngineeringProjectProjection",
    "EngineeringSessionCreateRequest",
    "EngineeringSessionSnapshot",
    "EngineeringWorkflowPreparationRequest",
    "EngineeringWorkflowUIProjection",
    "EngineeringWorkflowUnavailable",
    "HumanReviewUIProjection",
    "create_engineering_interface_runtime",
    "engineering_project_fingerprint",
)
