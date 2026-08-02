"""Composition root for the Engineering Interface Runtime."""

from embedded_copilot.engineering_interface.facade import EngineeringInterfaceRuntime
from embedded_copilot.engineering_interface.integration.workflow import (
    WorkflowPort,
    create_workflow_adapter,
)
from embedded_copilot.engineering_interface.runtime import _EngineeringInterfaceService


def create_engineering_interface_runtime(
    *,
    workflow_port: WorkflowPort,
) -> EngineeringInterfaceRuntime:
    adapter = create_workflow_adapter(workflow_port)
    return EngineeringInterfaceRuntime._compose(
        _EngineeringInterfaceService(workflow_adapter=adapter)
    )
