"""Metadata-only attachment projection for the local demo."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.web_api import (
    WebAttachmentProjection,
    WebAttachmentProjectionRequest,
    web_attachment_fingerprint,
)


class DemoAttachmentProjectionPort:
    """Return an immutable projection without reading attachment content."""

    __slots__ = ()

    def project(
        self, request: WebAttachmentProjectionRequest
    ) -> WebAttachmentProjection:
        checked = _typed_copy(request, WebAttachmentProjectionRequest)
        values = dict(
            project_id=checked.project_id,
            session_id=checked.session_id,
            reference_id=checked.reference_id,
            attachment_type=checked.attachment_type,
            basename=checked.basename,
            summary=checked.summary,
            size_bytes=checked.size_bytes,
            observed_at=checked.observed_at,
            source_fingerprint=checked.fingerprint,
        )
        return WebAttachmentProjection(
            **values,
            fingerprint=web_attachment_fingerprint(**values),
        )


def _typed_copy(value: object, expected_type: type):
    if type(value) is not expected_type:
        raise TypeError("typed attachment projection is required")
    try:
        return expected_type.model_validate(value.model_copy(deep=True))
    except (TypeError, ValueError, ValidationError):
        raise ValueError("attachment projection is invalid") from None
