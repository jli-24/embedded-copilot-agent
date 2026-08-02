"""Stateless orchestration for caller-owned Engineering Interface snapshots."""

from __future__ import annotations

from datetime import datetime

from embedded_copilot.engineering_interface.exceptions import (
    EngineeringInterfaceRejected,
    EngineeringWorkflowUnavailable,
)
from embedded_copilot.engineering_interface.integration.human_loop import (
    project_human_progress,
    project_human_review,
)
from embedded_copilot.engineering_interface.integration.workflow import (
    _WorkflowAdapter,
    project_workflow_progress,
)
from embedded_copilot.engineering_interface.models import (
    AttachmentProjectionRequest,
    EngineeringChatRequest,
    EngineeringChatRole,
    EngineeringProgressEvent,
    EngineeringProgressSource,
    EngineeringSessionCreateRequest,
    EngineeringSessionSnapshot,
    EngineeringWorkflowPreparationRequest,
    engineering_session_fingerprint,
    make_attachment_projection,
    make_message_projection,
    make_progress_event,
)


class _EngineeringInterfaceService:
    def __init__(self, *, workflow_adapter: _WorkflowAdapter) -> None:
        self._workflow_adapter = workflow_adapter

    def create_session(
        self,
        request: EngineeringSessionCreateRequest,
    ) -> EngineeringSessionSnapshot:
        try:
            checked = _typed_copy(request, EngineeringSessionCreateRequest)
            progress = (
                make_progress_event(
                    sequence=1,
                    session_id=checked.session_id,
                    source=EngineeringProgressSource.INTERFACE,
                    source_reference_id=checked.session_id,
                    source_sequence=1,
                    event="SESSION_CREATED",
                    state="ACTIVE",
                    count=0,
                    timestamp=checked.created_at,
                ),
            )
            return _snapshot(
                session_id=checked.session_id,
                title=checked.title,
                project=checked.project,
                created_at=checked.created_at,
                updated_at=checked.created_at,
                messages=(),
                attachments=(),
                workflows=(),
                human_reviews=(),
                progress_events=progress,
            )
        except Exception:
            raise EngineeringInterfaceRejected("interface request rejected") from None

    def submit_message(
        self,
        snapshot: EngineeringSessionSnapshot,
        request: EngineeringChatRequest,
    ) -> EngineeringSessionSnapshot:
        try:
            current = _typed_copy(snapshot, EngineeringSessionSnapshot)
            checked = _typed_copy(request, EngineeringChatRequest)
            _bind_session(current, checked.session_id, checked.timestamp)
            known_references = {item.reference_id for item in current.attachments}
            if not set(checked.reference_ids).issubset(known_references):
                raise ValueError("unknown attachment reference")
            if any(item.message_id == checked.message_id for item in current.messages):
                raise ValueError("duplicate message")
            messages = tuple(
                sorted(
                    (*current.messages, make_message_projection(checked)),
                    key=lambda item: (item.timestamp, item.message_id),
                )
            )
            progress = _append_interface_event(
                current,
                event="MESSAGE_PROJECTED",
                state="ACTIVE",
                count=len(messages),
                timestamp=checked.timestamp,
            )
            return _updated(
                current,
                updated_at=checked.timestamp,
                messages=messages,
                progress_events=progress,
            )
        except EngineeringInterfaceRejected:
            raise
        except Exception:
            raise EngineeringInterfaceRejected("interface request rejected") from None

    def project_attachment(
        self,
        snapshot: EngineeringSessionSnapshot,
        request: AttachmentProjectionRequest,
    ) -> EngineeringSessionSnapshot:
        try:
            current = _typed_copy(snapshot, EngineeringSessionSnapshot)
            checked = _typed_copy(request, AttachmentProjectionRequest)
            _bind_session(current, checked.session_id, checked.timestamp)
            if any(
                item.reference_id == checked.reference_id
                for item in current.attachments
            ):
                raise ValueError("duplicate attachment")
            attachment = make_attachment_projection(checked)
            attachments = tuple(
                sorted(
                    (*current.attachments, attachment),
                    key=lambda item: item.reference_id,
                )
            )
            progress = _append_interface_event(
                current,
                event="ATTACHMENT_PROJECTED",
                state="ACTIVE",
                count=len(attachments),
                timestamp=checked.timestamp,
            )
            return _updated(
                current,
                updated_at=checked.timestamp,
                attachments=attachments,
                progress_events=progress,
            )
        except Exception:
            raise EngineeringInterfaceRejected("interface request rejected") from None

    def prepare_workflow(
        self,
        snapshot: EngineeringSessionSnapshot,
        request: EngineeringWorkflowPreparationRequest,
    ) -> EngineeringSessionSnapshot:
        current = _checked_session(snapshot)
        try:
            checked = _typed_copy(request, EngineeringWorkflowPreparationRequest)
            _bind_session(current, checked.session_id, checked.requested_at)
            source = next(
                (
                    item
                    for item in current.messages
                    if item.message_id == checked.source_message_id
                ),
                None,
            )
            if source is None or source.role is not EngineeringChatRole.USER:
                raise ValueError("workflow source message is invalid")
            if any(
                item.workflow_id == checked.workflow_id for item in current.workflows
            ):
                raise ValueError("duplicate workflow")
            workflow = self._workflow_adapter.prepare(
                checked,
                requirement_summary=source.summary,
            )
            workflows = tuple(
                sorted(
                    (*current.workflows, workflow), key=lambda item: item.workflow_id
                )
            )
            progress = _append_interface_event(
                current,
                event="WORKFLOW_PROJECTED",
                state=workflow.state,
                count=len(workflows),
                timestamp=checked.requested_at,
            )
            return _updated(
                current,
                updated_at=checked.requested_at,
                workflows=workflows,
                progress_events=progress,
            )
        except EngineeringWorkflowUnavailable:
            raise
        except Exception:
            raise EngineeringInterfaceRejected("interface request rejected") from None

    def project_workflow_progress(
        self,
        snapshot: EngineeringSessionSnapshot,
        event: object,
    ) -> EngineeringSessionSnapshot:
        current = _checked_session(snapshot)
        projected = project_workflow_progress(
            session_id=current.session_id,
            sequence=len(current.progress_events) + 1,
            event=event,
        )
        return self._append_source_progress(current, projected)

    def project_human_loop_progress(
        self,
        snapshot: EngineeringSessionSnapshot,
        event: object,
    ) -> EngineeringSessionSnapshot:
        current = _checked_session(snapshot)
        projected = project_human_progress(
            session_id=current.session_id,
            sequence=len(current.progress_events) + 1,
            event=event,
        )
        return self._append_source_progress(current, projected)

    def project_human_review(
        self,
        snapshot: EngineeringSessionSnapshot,
        review: object,
    ) -> EngineeringSessionSnapshot:
        current = _checked_session(snapshot)
        projected = project_human_review(review)
        if any(
            item.proposal_id == projected.proposal_id for item in current.human_reviews
        ):
            raise EngineeringInterfaceRejected("interface request rejected") from None
        reviews = tuple(
            sorted(
                (*current.human_reviews, projected),
                key=lambda item: item.proposal_id,
            )
        )
        progress = _append_interface_event(
            current,
            event="HUMAN_REVIEW_PROJECTED",
            state=projected.state,
            count=len(reviews),
            timestamp=projected.reviewed_at,
        )
        try:
            return _updated(
                current,
                updated_at=projected.reviewed_at,
                human_reviews=reviews,
                progress_events=progress,
            )
        except Exception:
            raise EngineeringInterfaceRejected("interface request rejected") from None

    def _append_source_progress(
        self,
        current: EngineeringSessionSnapshot,
        projected: EngineeringProgressEvent,
    ) -> EngineeringSessionSnapshot:
        try:
            _bind_session(current, projected.session_id, projected.timestamp)
            prior = tuple(
                item.source_sequence
                for item in current.progress_events
                if item.source is projected.source
                and item.source_reference_id == projected.source_reference_id
            )
            expected = (prior[-1] + 1) if prior else 1
            if projected.source_sequence != expected:
                raise ValueError("source progress sequence is invalid")
            return _updated(
                current,
                updated_at=projected.timestamp,
                progress_events=(*current.progress_events, projected),
            )
        except Exception:
            raise EngineeringInterfaceRejected("interface request rejected") from None


def _typed_copy(value: object, expected_type):
    if type(value) is not expected_type:
        raise TypeError("typed contract is required")
    copied = value.model_copy(deep=True)
    return expected_type.model_validate(copied)


def _checked_session(value: object) -> EngineeringSessionSnapshot:
    try:
        return _typed_copy(value, EngineeringSessionSnapshot)
    except Exception:
        raise EngineeringInterfaceRejected("interface request rejected") from None


def _bind_session(
    snapshot: EngineeringSessionSnapshot,
    session_id: str,
    timestamp: datetime,
) -> None:
    if snapshot.session_id != session_id or timestamp < snapshot.updated_at:
        raise ValueError("session binding is invalid")


def _append_interface_event(
    snapshot: EngineeringSessionSnapshot,
    *,
    event: str,
    state: str,
    count: int,
    timestamp: datetime,
) -> tuple[EngineeringProgressEvent, ...]:
    source_sequence = 1 + sum(
        item.source is EngineeringProgressSource.INTERFACE
        for item in snapshot.progress_events
    )
    projected = make_progress_event(
        sequence=len(snapshot.progress_events) + 1,
        session_id=snapshot.session_id,
        source=EngineeringProgressSource.INTERFACE,
        source_reference_id=snapshot.session_id,
        source_sequence=source_sequence,
        event=event,
        state=state,
        count=count,
        timestamp=timestamp,
    )
    return (*snapshot.progress_events, projected)


def _snapshot(**values) -> EngineeringSessionSnapshot:
    return EngineeringSessionSnapshot(
        **values,
        fingerprint=engineering_session_fingerprint(**values),
    )


def _updated(
    current: EngineeringSessionSnapshot,
    *,
    updated_at: datetime,
    messages: tuple | None = None,
    attachments: tuple | None = None,
    workflows: tuple | None = None,
    human_reviews: tuple | None = None,
    progress_events: tuple | None = None,
) -> EngineeringSessionSnapshot:
    return _snapshot(
        session_id=current.session_id,
        title=current.title,
        project=current.project,
        created_at=current.created_at,
        updated_at=updated_at,
        messages=current.messages if messages is None else messages,
        attachments=current.attachments if attachments is None else attachments,
        workflows=current.workflows if workflows is None else workflows,
        human_reviews=(
            current.human_reviews if human_reviews is None else human_reviews
        ),
        progress_events=(
            current.progress_events if progress_events is None else progress_events
        ),
    )
