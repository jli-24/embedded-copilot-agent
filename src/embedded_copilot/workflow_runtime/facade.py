from __future__ import annotations

from embedded_copilot.workflow_runtime.contracts import EngineeringWorkflowPort


class WorkflowRuntime:
    __slots__ = ("_workflow_port",)

    def __init__(self, workflow_port: EngineeringWorkflowPort) -> None:
        raise TypeError("WorkflowRuntime must be created by the composition factory")

    @classmethod
    def _compose(cls, workflow_port: EngineeringWorkflowPort) -> WorkflowRuntime:
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_workflow_port", workflow_port)
        return runtime

    def workflow_port(self) -> EngineeringWorkflowPort:
        return self._workflow_port
