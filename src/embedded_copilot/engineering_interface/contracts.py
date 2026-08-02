"""Public Engineering Interface Protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.engineering_interface.models import (
    AttachmentProjectionRequest,
    EngineeringChatRequest,
    EngineeringSessionCreateRequest,
    EngineeringSessionSnapshot,
    EngineeringWorkflowPreparationRequest,
)


@runtime_checkable
class EngineeringInterfacePort(Protocol):
    def create_session(
        self,
        request: EngineeringSessionCreateRequest,
    ) -> EngineeringSessionSnapshot: ...

    def submit_message(
        self,
        snapshot: EngineeringSessionSnapshot,
        request: EngineeringChatRequest,
    ) -> EngineeringSessionSnapshot: ...

    def project_attachment(
        self,
        snapshot: EngineeringSessionSnapshot,
        request: AttachmentProjectionRequest,
    ) -> EngineeringSessionSnapshot: ...

    def prepare_workflow(
        self,
        snapshot: EngineeringSessionSnapshot,
        request: EngineeringWorkflowPreparationRequest,
    ) -> EngineeringSessionSnapshot: ...

    def project_workflow_progress(
        self,
        snapshot: EngineeringSessionSnapshot,
        event: object,
    ) -> EngineeringSessionSnapshot: ...

    def project_human_loop_progress(
        self,
        snapshot: EngineeringSessionSnapshot,
        event: object,
    ) -> EngineeringSessionSnapshot: ...

    def project_human_review(
        self,
        snapshot: EngineeringSessionSnapshot,
        review: object,
    ) -> EngineeringSessionSnapshot: ...
